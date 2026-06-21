"""Background scheduler — collects server metrics and checks alert thresholds."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as http_requests

from core.alerts import send_telegram
from core.auth import decrypt_value
from core.db import (
    cleanup_old_metrics,
    get_alert_config,
    get_all_servers,
    get_metrics,
    insert_alert,
    insert_metric,
)

log = logging.getLogger("adm.scheduler")

_stop = threading.Event()
_cooldowns: dict[tuple[int, str], float] = {}  # (server_id, alert_type) -> last_sent_ts
_last_cleanup: float = 0.0

POLL_INTERVAL = 300  # 5 minutes
COOLDOWN_SECONDS = 3600  # 1 hour between same alerts
CLEANUP_INTERVAL = 86400  # daily cleanup


def start_scheduler() -> None:
    """Start the background scheduler thread."""
    thread = threading.Thread(target=_loop, daemon=True, name="adm-scheduler")
    thread.start()
    log.info(f"Scheduler started, interval: {POLL_INTERVAL}s")


def stop_scheduler() -> None:
    """Signal the scheduler to stop."""
    _stop.set()


def _loop() -> None:
    # Wait a bit on startup to let app initialize
    _stop.wait(timeout=30)
    while not _stop.is_set():
        try:
            _collect_metrics()
            _check_alerts()
            _maybe_cleanup()
        except Exception:
            log.exception("Scheduler error")
        _stop.wait(timeout=POLL_INTERVAL)


def _agent_url(server: dict) -> str:
    return f"https://{server['ip']}:{server.get('agent_port', 5051)}"


def _agent_headers(server: dict) -> dict:
    headers = {}
    enc_key = server.get("agent_api_key_enc")
    if enc_key:
        api_key = decrypt_value(enc_key)
        if api_key:
            headers["X-API-Key"] = api_key
    return headers


def _poll_server(server: dict) -> dict:
    """Poll a single server's agent for status metrics."""
    result = {"online": False}
    try:
        url = _agent_url(server) + "/api/status"
        resp = http_requests.get(
            url, headers=_agent_headers(server), timeout=10, verify=False
        )
        data = resp.json()
        if data.get("ok"):
            status_data = data.get("data", {})
            result["online"] = True
            result["uptime"] = status_data.get("uptime")
            # Agent returns nested objects: disk.used_pct, memory.used_pct
            disk = status_data.get("disk", {})
            if isinstance(disk, dict):
                result["disk_pct"] = disk.get("used_pct")
            memory = status_data.get("memory", {})
            if isinstance(memory, dict):
                result["memory_pct"] = memory.get("used_pct")
            # Count services
            services = status_data.get("services", {})
            if services:
                result["services_ok"] = sum(
                    1 for v in services.values() if v is True or v == "active"
                )
            # Count running docker containers
            containers = status_data.get("docker_containers", [])
            if isinstance(containers, list):
                result["docker_ok"] = sum(
                    1 for c in containers
                    if isinstance(c, dict) and "up" in c.get("status", "").lower()
                )
    except http_requests.exceptions.RequestException:
        pass
    except Exception:
        log.debug(f"Error polling {server['name']}", exc_info=True)
    return result


def _collect_metrics() -> None:
    """Poll all active servers and store metrics."""
    servers = [s for s in get_all_servers() if s["status"] == "active"]
    if not servers:
        return

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(servers), 5)) as pool:
        futures = {pool.submit(_poll_server, s): s for s in servers}
        for future in as_completed(futures):
            server = futures[future]
            try:
                results[server["id"]] = future.result()
            except Exception:
                results[server["id"]] = {"online": False}

    for server in servers:
        metric = results.get(server["id"], {"online": False})
        insert_metric(server["id"], metric)

    log.info(
        f"Collected metrics for {len(servers)} server(s): "
        + ", ".join(
            f"{s['name']}={'up' if results.get(s['id'], {}).get('online') else 'down'}"
            for s in servers
        )
    )


def _check_alerts() -> None:
    """Check thresholds and send Telegram alerts if needed."""
    config = get_alert_config()
    if not config.get("enabled"):
        return

    bot_token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not bot_token or not chat_id:
        return

    disk_threshold = config.get("disk_threshold", 90.0)
    memory_threshold = config.get("memory_threshold", 90.0)
    offline_minutes = config.get("offline_minutes", 5)

    servers = [s for s in get_all_servers() if s["status"] == "active"]
    now = time.time()

    for server in servers:
        sid = server["id"]
        name = server["display_name"]

        # Get recent metrics (last 15 minutes)
        recent = get_metrics(server_id=sid, hours=1)
        if not recent:
            continue

        latest = recent[-1]

        # Check offline
        if not latest.get("online"):
            # Count how many consecutive offline readings
            offline_count = 0
            for m in reversed(recent):
                if not m.get("online"):
                    offline_count += 1
                else:
                    break

            offline_duration = offline_count * (POLL_INTERVAL / 60)
            if offline_duration >= offline_minutes:
                _maybe_send_alert(
                    sid, "offline", bot_token, chat_id,
                    f"*Server Offline*\nServer: {name}\n"
                    f"Down for: ~{int(offline_duration)} minutes",
                    now,
                )
            continue

        # Check disk
        disk = latest.get("disk_pct")
        if disk is not None and disk >= disk_threshold:
            _maybe_send_alert(
                sid, "disk", bot_token, chat_id,
                f"*Disk Warning*\nServer: {name}\n"
                f"Disk Usage: {disk:.1f}%",
                now,
            )

        # Check memory
        memory = latest.get("memory_pct")
        if memory is not None and memory >= memory_threshold:
            _maybe_send_alert(
                sid, "memory", bot_token, chat_id,
                f"*Memory Warning*\nServer: {name}\n"
                f"Memory Usage: {memory:.1f}%",
                now,
            )


def _maybe_send_alert(
    server_id: int, alert_type: str,
    bot_token: str, chat_id: str,
    message: str, now: float,
) -> None:
    """Send alert if cooldown has expired."""
    key = (server_id, alert_type)
    last_sent = _cooldowns.get(key, 0)
    if now - last_sent < COOLDOWN_SECONDS:
        return

    ok, error = send_telegram(bot_token, chat_id, message)
    if ok:
        _cooldowns[key] = now
        insert_alert(server_id, alert_type, message)
        log.info(f"Alert sent: {alert_type} for server {server_id}")
    else:
        log.error(f"Alert failed: {alert_type} for server {server_id}: {error}")


def _maybe_cleanup() -> None:
    """Delete old metrics once per day."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    deleted = cleanup_old_metrics(days=30)
    if deleted > 0:
        log.info(f"Cleaned up {deleted} old metric(s)")
