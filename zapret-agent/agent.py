"""Zapret Agent — lightweight management API for remote zapret nodes.

Runs on configurable port (HTTPS, default 5050), provides endpoints for:
- Health check
- Service status (nfqws2, shadowsocks)
- DPI args management
- Service restart
- SS key + ssconf URL generation
- Blockcheck (DPI strategy testing)

Auth: X-Sync-Key header must match config.json sync_key.
ssconf endpoint uses URL-embedded token for auth (standard ssconf protocol).
"""

import base64
import json
import os
import re
import socket
import subprocess
import threading
import time

from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_PATH = os.environ.get("ZAPRET_AGENT_CONFIG", "/opt/zapret-agent/config.json")
NFQWS2_CONF = "/opt/zapret/nfqws2.conf"
SS_CONFIG_FILE = "/etc/shadowsocks-libev/config.json"
NFQWS2_SERVICE = "zapret-nfqws2"
SS_SERVICE = "shadowsocks-libev-server@config"

# ── Config ──────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_sync_key() -> str:
    return _load_config().get("sync_key", "")


# ── Auth middleware ─────────────────────────────────────────────────────────

@app.before_request
def check_auth():
    # /health is public
    if request.path == "/health":
        return None
    # /ssconf/<token> uses URL-embedded token auth (checked in handler)
    if request.path.startswith("/ssconf/"):
        return None
    expected = _get_sync_key()
    if not expected:
        return None  # No key configured = open access
    provided = request.headers.get("X-Sync-Key", "")
    if provided != expected:
        return jsonify({"ok": False, "error": "Invalid or missing sync key"}), 403
    return None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _service_active(name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def _read_dpi_args() -> str:
    """Read DPI args from nfqws2.conf, stripping the --qnum line."""
    try:
        with open(NFQWS2_CONF) as f:
            lines = f.read().strip().splitlines()
        # Return everything except --qnum=... lines
        dpi_lines = [l for l in lines if not l.strip().startswith("--qnum")]
        return "\n".join(dpi_lines).strip()
    except Exception:
        return ""


def _read_ss_config() -> dict | None:
    try:
        with open(SS_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _get_public_ip() -> str | None:
    try:
        result = subprocess.run(
            ["curl", "-4", "-s", "--max-time", "5", "https://ifconfig.me"],
            capture_output=True, text=True, timeout=10,
        )
        ip = result.stdout.strip()
        return ip if ip else None
    except Exception:
        return None


def _get_uptime() -> int:
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "hostname": socket.gethostname(),
        "uptime": _get_uptime(),
    })


@app.get("/api/status")
def get_status():
    ss_config = _read_ss_config()
    return jsonify({
        "ok": True,
        "data": {
            "hostname": socket.gethostname(),
            "nfqws2_active": _service_active(NFQWS2_SERVICE),
            "ss_active": _service_active(SS_SERVICE),
            "dpi_args": _read_dpi_args(),
            "ss_config": {
                "port": ss_config.get("server_port", 8388),
                "method": ss_config.get("method", "chacha20-ietf-poly1305"),
            } if ss_config else None,
            "public_ip": _get_public_ip(),
            "uptime": _get_uptime(),
        },
    })


@app.get("/api/dpi-args")
def get_dpi_args():
    return jsonify({"ok": True, "data": _read_dpi_args()})


@app.put("/api/dpi-args")
def update_dpi_args():
    body = request.get_json(force=True, silent=True) or {}
    new_args = body.get("dpi_args", "").strip()
    if not new_args:
        return jsonify({"ok": False, "error": "dpi_args is required"}), 400

    # Read current conf to preserve --qnum value
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

    # Restart nfqws2 to apply new args
    try:
        subprocess.run(
            ["systemctl", "restart", NFQWS2_SERVICE],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Args saved but restart failed: {e}"}), 500

    return jsonify({"ok": True})


@app.post("/api/restart")
def restart_services():
    body = request.get_json(force=True, silent=True) or {}
    services = body.get("services", ["nfqws2", "ss"])
    results = {}

    if "nfqws2" in services:
        try:
            subprocess.run(
                ["systemctl", "restart", NFQWS2_SERVICE],
                capture_output=True, text=True, timeout=15,
            )
            results["nfqws2"] = "restarted"
        except Exception as e:
            results["nfqws2"] = f"error: {e}"

    if "ss" in services:
        try:
            subprocess.run(
                ["systemctl", "restart", SS_SERVICE],
                capture_output=True, text=True, timeout=15,
            )
            results["ss"] = "restarted"
        except Exception as e:
            results["ss"] = f"error: {e}"

    return jsonify({"ok": True, "data": results})


@app.get("/api/ss-key")
def get_ss_key():
    ss_config = _read_ss_config()
    if not ss_config:
        return jsonify({"ok": False, "error": "SS config not found"}), 404

    method = ss_config.get("method", "chacha20-ietf-poly1305")
    password = ss_config.get("password", "")
    port = ss_config.get("server_port", 8388)

    # Get server IP from agent config or detect
    config = _load_config()
    server_ip = config.get("server_ip") or _get_public_ip() or socket.gethostname()
    node_name = config.get("node_name", socket.gethostname())

    # Build ss:// URI
    user_info = base64.b64encode(f"{method}:{password}".encode()).decode()
    ss_uri = f"ss://{user_info}@{server_ip}:{port}#{node_name}"

    # Build ssconf:// URL (points to this agent's /ssconf endpoint)
    sync_key = config.get("sync_key", "")
    # external_port allows different public port (e.g. when NAT maps 5051→5050)
    ssconf_port = config.get("external_port") or config.get("agent_port", 5050)
    ssconf_url = f"ssconf://{server_ip}:{ssconf_port}/ssconf/{sync_key}"

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
    """Serve SS config in ssconf/SIP008 format.

    The URL token serves as authentication (standard ssconf protocol).
    This endpoint is what Proxima fetches when you add an ssconf:// key.
    """
    expected = _get_sync_key()
    if not expected or token != expected:
        return jsonify({"error": "Invalid token"}), 401

    ss_config = _read_ss_config()
    if not ss_config:
        return jsonify({"error": "SS config not found"}), 404

    config = _load_config()
    server_ip = config.get("server_ip") or _get_public_ip() or socket.gethostname()

    return jsonify({
        "server": server_ip,
        "server_port": ss_config.get("server_port", 8388),
        "password": ss_config.get("password", ""),
        "method": ss_config.get("method", "chacha20-ietf-poly1305"),
    })


# ── Blockcheck ──────────────────────────────────────────────────────────────

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

        # Test baseline (without DPI bypass)
        baseline_code = None
        dpi_code = None

        try:
            # Baseline: direct curl
            res = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", str(timeout), f"https://{domain}"],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            baseline_code = res.stdout.strip() or "000"
        except Exception:
            baseline_code = "000"

        try:
            # Stop nfqws2, start with test strategy, curl, stop, restart original
            subprocess.run(["systemctl", "stop", NFQWS2_SERVICE],
                           capture_output=True, timeout=10)

            dpi_args = strategy.split()
            nfqws_proc = subprocess.Popen(
                ["/opt/zapret/bin/nfqws2", "--qnum=999"] + dpi_args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

            # Add iptables rule for test queue
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

        except Exception as e:
            dpi_code = "000"

        finally:
            # Cleanup: remove test iptables rule, kill test nfqws, restart original
            subprocess.run(
                ["iptables", "-t", "mangle", "-D", "OUTPUT",
                 "-p", "tcp", "--dport", "443",
                 "-m", "connbytes", "--connbytes-dir=original",
                 "--connbytes-mode=packets", "--connbytes", "1:15",
                 "-j", "NFQUEUE", "--queue-num", "999", "--queue-bypass"],
                capture_output=True, timeout=5,
            )
            try:
                nfqws_proc.terminate()
                nfqws_proc.wait(timeout=3)
            except Exception:
                try:
                    nfqws_proc.kill()
                except Exception:
                    pass
            subprocess.run(["systemctl", "start", NFQWS2_SERVICE],
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


# ── Main ────────────────────────────────────────────────────────────────────

CERT_FILE = "/opt/zapret-agent/cert.pem"
KEY_FILE = "/opt/zapret-agent/key.pem"


def _ensure_tls_cert():
    """Generate self-signed TLS cert if it doesn't exist."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", KEY_FILE, "-out", CERT_FILE,
        "-days", "3650", "-nodes",
        "-subj", "/CN=zapret-agent",
    ], check=True, capture_output=True)


if __name__ == "__main__":
    _ensure_tls_cert()
    config = _load_config()
    port = config.get("agent_port", 5050)
    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        ssl_context=(CERT_FILE, KEY_FILE),
    )
