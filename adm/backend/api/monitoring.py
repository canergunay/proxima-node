"""Monitoring API — metrics, alerts, config."""

import logging

from flask import Blueprint, jsonify, request

from core.alerts import send_telegram
from core.db import (
    get_alert_config,
    get_all_servers,
    get_metrics,
    get_recent_alerts,
    update_alert_config,
)

log = logging.getLogger("adm.monitoring")
bp = Blueprint("monitoring", __name__)


@bp.get("/api/monitoring/metrics")
def metrics():
    """Time-series metrics. Params: server_id (optional), hours (default 24, max 720)."""
    server_id = request.args.get("server_id", type=int)
    hours = request.args.get("hours", 24, type=int)
    hours = min(max(hours, 1), 720)

    data = get_metrics(server_id=server_id, hours=hours)

    # Build server name map
    servers = {}
    for s in get_all_servers():
        servers[str(s["id"])] = {
            "name": s["name"],
            "display_name": s["display_name"],
        }

    return jsonify({
        "ok": True,
        "data": {
            "servers": servers,
            "metrics": data,
        },
    })


@bp.get("/api/monitoring/alerts")
def alerts():
    """Recent alert history."""
    limit = request.args.get("limit", 100, type=int)
    data = get_recent_alerts(limit=min(limit, 500))
    return jsonify({"ok": True, "data": data})


@bp.get("/api/monitoring/config")
def get_config():
    """Alert configuration (token masked)."""
    config = get_alert_config()
    # Mask the bot token for security
    token = config.get("telegram_bot_token", "")
    if token and len(token) > 8:
        config["telegram_bot_token"] = token[:4] + "..." + token[-4:]
    return jsonify({"ok": True, "data": config})


@bp.put("/api/monitoring/config")
def put_config():
    """Update alert configuration."""
    body = request.get_json(silent=True) or {}

    updates = {}
    if "enabled" in body:
        updates["enabled"] = 1 if body["enabled"] else 0
    if "telegram_bot_token" in body:
        updates["telegram_bot_token"] = body["telegram_bot_token"]
    if "telegram_chat_id" in body:
        updates["telegram_chat_id"] = body["telegram_chat_id"]
    if "disk_threshold" in body:
        updates["disk_threshold"] = float(body["disk_threshold"])
    if "memory_threshold" in body:
        updates["memory_threshold"] = float(body["memory_threshold"])
    if "cpu_threshold" in body:
        updates["cpu_threshold"] = float(body["cpu_threshold"])
    if "offline_minutes" in body:
        updates["offline_minutes"] = int(body["offline_minutes"])

    if not updates:
        return jsonify({"ok": False, "error": "No valid fields"}), 400

    update_alert_config(updates)
    return jsonify({"ok": True})


@bp.post("/api/monitoring/test-alert")
def test_alert():
    """Send a test Telegram message."""
    config = get_alert_config()
    bot_token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")

    if not bot_token or not chat_id:
        return jsonify({"ok": False, "error": "Telegram not configured"}), 400

    ok, error = send_telegram(
        bot_token, chat_id,
        "*Proxima ADM — Test Alert*\nThis is a test notification from ADM monitoring."
    )

    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": error}), 502
