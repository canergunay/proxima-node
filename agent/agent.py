"""proxima-agent — Universal management agent for Proxima server nodes.

Runs on port 5051 (HTTPS), provides endpoints for:
- Health check and status monitoring
- Service management (restart, status)
- SS key retrieval + ssconf URL
- DPI args management (DPI bypass nodes)
- Blockcheck DPI strategy testing (DPI bypass nodes)

Auth: X-API-Key header must match config api_key.
ssconf endpoint uses URL-embedded token for auth (standard ssconf protocol).

Server type is auto-detected based on installed services.
"""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time

from flask import Flask, jsonify, request

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

AGENT_DIR = os.environ.get("PROXIMA_AGENT_DIR", "/opt/proxima-agent")
CONFIG_PATH = os.environ.get("PROXIMA_AGENT_CONFIG", f"{AGENT_DIR}/config.json")
CERT_FILE = f"{AGENT_DIR}/cert.pem"
KEY_FILE = f"{AGENT_DIR}/key.pem"
VERSION = "2.1.0"

# Service paths by server type
OUTLINE_SS_CONFIG = "/opt/outline-ss/config.yml"
SS_LIBEV_CONFIG = "/etc/shadowsocks-libev/config.json"
NFQWS2_CONF = "/opt/zapret/nfqws2.conf"

# Service names
SVC_OUTLINE_SS = "outline-ss-server"
SVC_SS_LIBEV = "shadowsocks-libev-server@config"
SVC_NFQWS2 = "zapret-nfqws2"
SVC_SSCONF = "proxima-ssconf"
SVC_SPEEDTEST = "proxima-speedtest"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_api_key() -> str:
    return _load_config().get("api_key", "")


# ── Server type detection ──────────────────────────────────────────────────

def _detect_server_type() -> str:
    """Auto-detect server type based on installed services."""
    if _service_exists(SVC_NFQWS2):
        return "dpi_bypass"
    if _service_exists(SVC_OUTLINE_SS):
        return "vpn_exit"
    return "unknown"


def _service_exists(name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "cat", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ── Auth middleware ─────────────────────────────────────────────────────────

@app.before_request
def check_auth():
    # /health is public
    if request.path == "/health":
        return None
    # /ssconf/<token> uses URL-embedded token auth
    if request.path.startswith("/ssconf/"):
        return None
    expected = _get_api_key()
    if not expected:
        return None  # No key configured = open access (dev mode)
    provided = request.headers.get("X-API-Key", "")
    # Also accept legacy X-Sync-Key header for backward compat
    if not provided:
        provided = request.headers.get("X-Sync-Key", "")
    if provided != expected:
        return jsonify({"ok": False, "error": "Invalid or missing API key"}), 403
    return None


# ── Helpers ────────────────────────────────────────────────────────────────

def _service_active(name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def _get_public_ip() -> str | None:
    for url in ["https://ifconfig.me", "https://api.ipify.org", "https://icanhazip.com"]:
        try:
            result = subprocess.run(
                ["curl", "-4", "-s", "--max-time", "5", url],
                capture_output=True, text=True, timeout=10,
            )
            ip = result.stdout.strip()
            if ip:
                return ip
        except Exception:
            continue
    return None


def _get_uptime() -> int:
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


def _get_disk_usage() -> dict:
    try:
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "used_pct": round(used / total * 100, 1),
        }
    except Exception:
        return {}


def _get_memory() -> dict:
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])  # kB
                    info[key] = val
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            return {
                "total_mb": round(total / 1024),
                "available_mb": round(available / 1024),
                "used_pct": round((total - available) / total * 100, 1) if total else 0,
            }
    except Exception:
        return {}


def _get_docker_containers() -> list:
    """List running Docker containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Image}} {{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        containers = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                containers.append({
                    "name": parts[0],
                    "image": parts[1],
                    "status": parts[2] if len(parts) > 2 else "",
                })
        return containers
    except Exception:
        return []


# ── SS config readers ──────────────────────────────────────────────────────

def _read_outline_ss_config() -> dict | None:
    """Read outline-ss-server config.yml."""
    try:
        with open(OUTLINE_SS_CONFIG) as f:
            content = f.read()
        # Simple YAML parsing for our known format
        password = re.search(r'secret:\s*"([^"]*)"', content)
        prefix = re.search(r'prefix:\s*"([^"]*)"', content)
        port = re.search(r'address:\s*"\[::\]:(\d+)"', content)
        cipher = re.search(r'cipher:\s*"?(\S+?)"?\s*$', content, re.MULTILINE)
        return {
            "password": password.group(1) if password else "",
            "prefix": prefix.group(1) if prefix else "",
            "port": int(port.group(1)) if port else 8388,
            "method": cipher.group(1) if cipher else "chacha20-ietf-poly1305",
        }
    except Exception:
        return None


def _read_ss_libev_config() -> dict | None:
    """Read shadowsocks-libev config.json."""
    try:
        with open(SS_LIBEV_CONFIG) as f:
            cfg = json.load(f)
        return {
            "password": cfg.get("password", ""),
            "port": cfg.get("server_port", 8388),
            "method": cfg.get("method", "chacha20-ietf-poly1305"),
        }
    except Exception:
        return None


def _read_ss_config() -> dict | None:
    """Read SS config from whichever implementation is installed."""
    cfg = _read_outline_ss_config()
    if cfg:
        return cfg
    return _read_ss_libev_config()


# ── DPI-specific helpers ───────────────────────────────────────────────────

def _read_dpi_args() -> str:
    try:
        with open(NFQWS2_CONF) as f:
            lines = f.read().strip().splitlines()
        return "\n".join(l for l in lines if not l.strip().startswith("--qnum")).strip()
    except Exception:
        return ""


# ── Universal endpoints ────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "hostname": socket.gethostname(),
        "version": VERSION,
        "uptime": _get_uptime(),
    })


@app.get("/api/info")
def get_info():
    server_type = _detect_server_type()
    config = _load_config()
    return jsonify({
        "ok": True,
        "data": {
            "version": VERSION,
            "server_type": server_type,
            "hostname": socket.gethostname(),
            "node_id": config.get("node_id", ""),
            "agent_port": config.get("agent_port", 5051),
        },
    })


@app.get("/api/status")
def get_status():
    server_type = _detect_server_type()
    config = _load_config()

    data = {
        "hostname": socket.gethostname(),
        "server_type": server_type,
        "public_ip": _get_public_ip(),
        "uptime": _get_uptime(),
        "disk": _get_disk_usage(),
        "memory": _get_memory(),
        "docker_containers": _get_docker_containers(),
    }

    if server_type == "vpn_exit":
        ss_cfg = _read_outline_ss_config()
        data["services"] = {
            "outline_ss": _service_active(SVC_OUTLINE_SS),
            "ssconf": _service_active(SVC_SSCONF),
            "speedtest": _service_active(SVC_SPEEDTEST),
        }
        data["ss_config"] = {
            "port": ss_cfg.get("port", 8388) if ss_cfg else 8388,
            "method": ss_cfg.get("method", "chacha20-ietf-poly1305") if ss_cfg else "",
        }

    elif server_type == "dpi_bypass":
        ss_cfg = _read_ss_libev_config()
        data["services"] = {
            "nfqws2": _service_active(SVC_NFQWS2),
            "ss_server": _service_active(SVC_SS_LIBEV),
        }
        data["dpi_args"] = _read_dpi_args()
        data["ss_config"] = {
            "port": ss_cfg.get("port", 8388) if ss_cfg else 8388,
            "method": ss_cfg.get("method", "chacha20-ietf-poly1305") if ss_cfg else "",
        }

    return jsonify({"ok": True, "data": data})


@app.get("/api/health")
def deep_health():
    """Deep health check — verifies SS connectivity and service states."""
    server_type = _detect_server_type()
    checks = {}

    if server_type == "vpn_exit":
        checks["outline_ss"] = _service_active(SVC_OUTLINE_SS)
        checks["ssconf"] = _service_active(SVC_SSCONF)
    elif server_type == "dpi_bypass":
        checks["nfqws2"] = _service_active(SVC_NFQWS2)
        checks["ss_server"] = _service_active(SVC_SS_LIBEV)

    checks["public_ip"] = _get_public_ip() is not None
    all_ok = all(checks.values())

    return jsonify({"ok": all_ok, "data": checks})


@app.post("/api/restart")
def restart_services():
    body = request.get_json(force=True, silent=True) or {}
    services = body.get("services", [])
    results = {}

    service_map = {
        "outline-ss": SVC_OUTLINE_SS,
        "ss-server": SVC_SS_LIBEV,
        "nfqws2": SVC_NFQWS2,
        "ssconf": SVC_SSCONF,
        "speedtest": SVC_SPEEDTEST,
        # Legacy names (backward compat)
        "ss": SVC_SS_LIBEV,
    }

    for svc_name in services:
        systemd_name = service_map.get(svc_name, svc_name)
        try:
            subprocess.run(
                ["systemctl", "restart", systemd_name],
                capture_output=True, text=True, timeout=15,
            )
            results[svc_name] = "restarted"
        except Exception as e:
            results[svc_name] = f"error: {e}"

    return jsonify({"ok": True, "data": results})


@app.get("/api/ss-key")
def get_ss_key():
    ss_cfg = _read_ss_config()
    if not ss_cfg:
        return jsonify({"ok": False, "error": "SS config not found"}), 404

    config = _load_config()
    server_ip = config.get("server_ip") or _get_public_ip() or socket.gethostname()
    node_id = config.get("node_id", socket.gethostname())
    api_key = config.get("api_key", "")
    method = ss_cfg.get("method", "chacha20-ietf-poly1305")
    password = ss_cfg.get("password", "")
    port = ss_cfg.get("port", 8388)

    # Build ss:// URI (SIP002 format — URL-safe base64)
    user_info = base64.urlsafe_b64encode(f"{method}:{password}".encode()).decode().rstrip("=")
    ss_uri = f"ss://{user_info}@{server_ip}:{port}#{node_id}"

    # Build ssconf URL
    ssconf_url = ""
    ssconf_token = config.get("ssconf_token") or api_key
    server_type = _detect_server_type()
    if ssconf_token:
        if server_type == "vpn_exit" and _service_active(SVC_SSCONF):
            # VPN exit: dedicated ssconf service on port 8390
            ssconf_url = f"ssconf://{server_ip}:8390/{ssconf_token}"
        else:
            # All types: agent serves ssconf on its own port at /ssconf/<token>
            agent_port = config.get("agent_port", 5051)
            ssconf_url = f"ssconf://{server_ip}:{agent_port}/ssconf/{ssconf_token}"

    return jsonify({
        "ok": True,
        "data": {
            "uri": ss_uri,
            "ssconf_url": ssconf_url,
            "server": server_ip,
            "port": port,
            "method": method,
            "password": password,
        },
    })


@app.get("/ssconf/<token>")
def ssconf_config(token: str):
    """Serve SS config in ssconf/SIP008 format."""
    config = _load_config()
    expected = config.get("ssconf_token") or _get_api_key()
    if not expected or token != expected:
        return jsonify({"error": "Invalid token"}), 401

    ss_cfg = _read_ss_config()
    if not ss_cfg:
        return jsonify({"error": "SS config not found"}), 404

    config = _load_config()
    server_ip = config.get("server_ip") or _get_public_ip() or socket.gethostname()

    response = {
        "server": server_ip,
        "server_port": ss_cfg.get("port", 8388),
        "password": ss_cfg.get("password", ""),
        "method": ss_cfg.get("method", "chacha20-ietf-poly1305"),
    }
    prefix = ss_cfg.get("prefix", "")
    if prefix:
        response["prefix"] = prefix

    return jsonify(response)


# ── VPN Exit endpoints ─────────────────────────────────────────────────────

@app.put("/api/ss-config")
def update_ss_config():
    """Update SS credentials (VPN exit nodes)."""
    if _detect_server_type() != "vpn_exit":
        return jsonify({"ok": False, "error": "Only available on VPN exit nodes"}), 400

    body = request.get_json(force=True, silent=True) or {}
    password = body.get("password", "").strip()
    if not password:
        return jsonify({"ok": False, "error": "password is required"}), 400

    # Read current config and update password
    try:
        with open(OUTLINE_SS_CONFIG) as f:
            content = f.read()
        content = re.sub(r'secret:\s*"[^"]*"', f'secret: "{password}"', content)
        prefix = body.get("prefix", "").strip()
        if prefix:
            content = re.sub(r'prefix:\s*"[^"]*"', f'prefix: "{prefix}"', content)
        with open(OUTLINE_SS_CONFIG, "w") as f:
            f.write(content)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to update config: {e}"}), 500

    # Restart outline-ss
    try:
        subprocess.run(
            ["systemctl", "restart", SVC_OUTLINE_SS],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Config updated but restart failed: {e}"}), 500

    return jsonify({"ok": True})


# ── DPI Bypass endpoints ───────────────────────────────────────────────────

@app.get("/api/dpi-args")
def get_dpi_args():
    return jsonify({"ok": True, "data": _read_dpi_args()})


@app.put("/api/dpi-args")
def update_dpi_args():
    if _detect_server_type() != "dpi_bypass":
        return jsonify({"ok": False, "error": "Only available on DPI bypass nodes"}), 400

    body = request.get_json(force=True, silent=True) or {}
    new_args = body.get("dpi_args", "").strip()
    if not new_args:
        return jsonify({"ok": False, "error": "dpi_args is required"}), 400

    # Preserve --qnum value
    qnum = "200"
    try:
        with open(NFQWS2_CONF) as f:
            for line in f:
                if line.strip().startswith("--qnum"):
                    qnum = line.strip().split("=", 1)[1] if "=" in line.strip() else "200"
                    break
    except Exception:
        pass

    try:
        with open(NFQWS2_CONF, "w") as f:
            f.write(f"--qnum={qnum}\n{new_args}\n")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to write: {e}"}), 500

    try:
        subprocess.run(
            ["systemctl", "restart", SVC_NFQWS2],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Args saved but restart failed: {e}"}), 500

    return jsonify({"ok": True})


@app.get("/api/zapret-status")
def zapret_status():
    """Get zapret-specific status (iptables rules, watchdog)."""
    if _detect_server_type() != "dpi_bypass":
        return jsonify({"ok": False, "error": "Only available on DPI bypass nodes"}), 400

    # Check iptables rules
    uid_rule_ok = False
    nfqueue_rule_ok = False
    try:
        result = subprocess.run(
            ["iptables", "-t", "mangle", "-L", "OUTPUT", "-n"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout
        uid_rule_ok = "owner UID match" in output
        nfqueue_rule_ok = "NFQUEUE" in output
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "data": {
            "nfqws2_active": _service_active(SVC_NFQWS2),
            "uid_exception_rule": uid_rule_ok,
            "nfqueue_rule": nfqueue_rule_ok,
            "watchdog_active": _service_active("zapret-watchdog.timer"),
            "dpi_args": _read_dpi_args(),
        },
    })


# ── Blockcheck ─────────────────────────────────────────────────────────────

_bc_lock = threading.Lock()
_bc_run: dict | None = None


def _blockcheck_thread(domain: str, strategies: list[str], timeout: int) -> None:
    """Run DPI strategy tests sequentially."""
    global _bc_run
    results = []

    for idx, strategy in enumerate(strategies):
        with _bc_lock:
            if not _bc_run or _bc_run.get("status") == "cancelled":
                return
            _bc_run["current_index"] = idx
            _bc_run["current_strategy"] = strategy

        baseline_code = None
        dpi_code = None

        try:
            res = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", str(timeout), f"https://{domain}"],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            baseline_code = res.stdout.strip() or "000"
        except Exception:
            baseline_code = "000"

        nfqws_proc = None
        try:
            subprocess.run(["systemctl", "stop", SVC_NFQWS2],
                           capture_output=True, timeout=10)

            dpi_args = strategy.split()
            nfqws_proc = subprocess.Popen(
                ["/opt/zapret/bin/nfqws2", "--qnum=999"] + dpi_args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

            subprocess.run(
                ["iptables", "-t", "mangle", "-I", "OUTPUT",
                 "-p", "tcp", "--dport", "443",
                 "-m", "connbytes", "--connbytes-dir=original",
                 "--connbytes-mode=packets", "--connbytes", "1:15",
                 "-j", "NFQUEUE", "--queue-num", "999", "--queue-bypass"],
                capture_output=True, timeout=5,
            )

            time.sleep(0.5)

            res = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", str(timeout), f"https://{domain}"],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            dpi_code = res.stdout.strip() or "000"

        except Exception:
            dpi_code = "000"

        finally:
            subprocess.run(
                ["iptables", "-t", "mangle", "-D", "OUTPUT",
                 "-p", "tcp", "--dport", "443",
                 "-m", "connbytes", "--connbytes-dir=original",
                 "--connbytes-mode=packets", "--connbytes", "1:15",
                 "-j", "NFQUEUE", "--queue-num", "999", "--queue-bypass"],
                capture_output=True, timeout=5,
            )
            if nfqws_proc:
                try:
                    nfqws_proc.terminate()
                    nfqws_proc.wait(timeout=3)
                except Exception:
                    try:
                        nfqws_proc.kill()
                    except Exception:
                        pass
            subprocess.run(["systemctl", "start", SVC_NFQWS2],
                           capture_output=True, timeout=10)

        dpi_success = False
        try:
            code = int(dpi_code)
            dpi_success = 200 <= code < 400
        except (ValueError, TypeError):
            pass

        results.append({
            "index": idx,
            "strategy": strategy,
            "baseline_code": baseline_code,
            "dpi_code": dpi_code,
            "available": dpi_success,
        })

        with _bc_lock:
            if _bc_run:
                _bc_run["results"] = list(results)

    with _bc_lock:
        if _bc_run and _bc_run.get("status") != "cancelled":
            _bc_run["status"] = "done"
            _bc_run["completed_at"] = time.time()
            _bc_run["current_strategy"] = None


@app.post("/api/blockcheck/start")
def start_blockcheck():
    global _bc_run
    if _detect_server_type() != "dpi_bypass":
        return jsonify({"ok": False, "error": "Only available on DPI bypass nodes"}), 400

    body = request.get_json(force=True, silent=True) or {}
    domain = body.get("domain", "").strip()
    strategies = body.get("strategies", [])
    timeout = min(max(int(body.get("timeout", 5)), 2), 15)

    if not domain:
        return jsonify({"ok": False, "error": "domain is required"}), 400
    if not strategies or not isinstance(strategies, list):
        return jsonify({"ok": False, "error": "strategies list is required"}), 400
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*\.)+[a-zA-Z]{2,}$', domain):
        return jsonify({"ok": False, "error": "Invalid domain format"}), 400

    strategies = [s.strip() for s in strategies if s.strip()]
    if not strategies:
        return jsonify({"ok": False, "error": "No valid strategies"}), 400

    with _bc_lock:
        if _bc_run and _bc_run.get("status") == "running":
            return jsonify({"ok": False, "error": "A test is already running"}), 409

        _bc_run = {
            "status": "running",
            "domain": domain,
            "strategies": strategies,
            "total": len(strategies),
            "current_index": 0,
            "current_strategy": strategies[0],
            "results": [],
            "started_at": time.time(),
            "completed_at": None,
        }

    thread = threading.Thread(
        target=_blockcheck_thread,
        args=(domain, strategies, timeout),
        daemon=True,
    )
    thread.start()

    return jsonify({"ok": True, "data": {"total": len(strategies)}})


@app.get("/api/blockcheck/status")
def get_blockcheck_status():
    with _bc_lock:
        state = dict(_bc_run) if _bc_run else None
    if not state:
        return jsonify({"ok": True, "data": None})
    return jsonify({"ok": True, "data": state})


@app.post("/api/blockcheck/stop")
def stop_blockcheck():
    global _bc_run
    with _bc_lock:
        if not _bc_run or _bc_run.get("status") != "running":
            return jsonify({"ok": False, "error": "No test running"}), 400
        _bc_run["status"] = "cancelled"
        _bc_run["completed_at"] = time.time()
    return jsonify({"ok": True})


# ── Healthchecks.io push ──────────────────────────────────────────────────

_HC_INTERVAL = 300  # 5 minutes


def _healthcheck_ping():
    """Background thread: ping healthchecks.io every 5 minutes.

    Sends success ping if all critical services are running and public IP
    is reachable. Sends fail ping otherwise.
    Config key: "healthchecks_url" — the ping URL from healthchecks.io.
    """
    while True:
        try:
            config = _load_config()
            hc_url = config.get("healthchecks_url", "").strip()
            if not hc_url:
                time.sleep(_HC_INTERVAL)
                continue

            server_type = _detect_server_type()
            ok = True

            if server_type == "vpn_exit":
                ok = _service_active(SVC_OUTLINE_SS)
            elif server_type == "dpi_bypass":
                ok = _service_active(SVC_NFQWS2) and _service_active(SVC_SS_LIBEV)

            if ok:
                ok = _get_public_ip() is not None

            ping_url = f"{hc_url.rstrip('/')}/fail" if not ok else hc_url
            subprocess.run(
                ["curl", "-4", "-s", "--max-time", "10", "-o", "/dev/null", ping_url],
                capture_output=True, timeout=15,
            )
        except Exception:
            pass

        time.sleep(_HC_INTERVAL)


# ── TLS cert management ───────────────────────────────────────────────────

def _ensure_tls_cert():
    """Generate self-signed TLS cert if it doesn't exist."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    os.makedirs(AGENT_DIR, exist_ok=True)
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "ec",
        "-pkeyopt", "ec_paramgen_curve:prime256v1",
        "-keyout", KEY_FILE, "-out", CERT_FILE,
        "-days", "3650", "-nodes",
        "-subj", "/CN=proxima-agent",
    ], check=True, capture_output=True)
    os.chmod(KEY_FILE, 0o600)
    os.chmod(CERT_FILE, 0o644)


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_tls_cert()
    config = _load_config()
    port = config.get("agent_port", 5051)
    server_type = _detect_server_type()

    # Start healthchecks.io push thread if configured
    hc_url = config.get("healthchecks_url", "")
    if hc_url:
        hc_thread = threading.Thread(target=_healthcheck_ping, daemon=True)
        hc_thread.start()
        print(f"  healthchecks.io push enabled", flush=True)

    print(f"proxima-agent v{VERSION} starting on :{port} (type={server_type})", flush=True)
    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        ssl_context=(CERT_FILE, KEY_FILE),
    )
