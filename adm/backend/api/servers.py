"""Server management API — CRUD + agent proxy endpoints."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as http_requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Blueprint, jsonify, request

from core.auth import decrypt_value, encrypt_value
from core.db import (
    create_server,
    delete_server,
    get_all_servers,
    get_operations_by_server,
    get_server,
    update_server,
)

log = logging.getLogger("adm.servers")
bp = Blueprint("servers", __name__)


# ── Agent proxy helpers ──────────────────────────────────────────────────

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


def _proxy_request(server: dict, method: str, path: str,
                   body: dict | None = None, timeout: int = 15) -> dict:
    """Forward an HTTP request to a proxima-agent."""
    url = _agent_url(server) + path
    headers = _agent_headers(server)

    if method == "GET":
        resp = http_requests.get(url, headers=headers, timeout=timeout, verify=False)
    elif method == "POST":
        resp = http_requests.post(url, json=body, headers=headers, timeout=timeout, verify=False)
    elif method == "PUT":
        resp = http_requests.put(url, json=body, headers=headers, timeout=timeout, verify=False)
    else:
        raise ValueError(f"Unsupported method: {method}")

    resp.raise_for_status()
    return resp.json()


def _fetch_server_status(server: dict) -> dict:
    """Fetch live status from a single server's agent."""
    result = {
        "id": server["id"],
        "name": server["name"],
        "display_name": server["display_name"],
        "ip": server["ip"],
        "server_type": server["server_type"],
        "location": server["location"],
        "provider": server["provider"],
        "status": server["status"],
        "agent_port": server.get("agent_port", 5051),
        "online": False,
        "agent_status": None,
        "error": None,
    }

    if server["status"] in ("new", "decommissioned"):
        return result

    try:
        data = _proxy_request(server, "GET", "/api/status", timeout=10)
        if data.get("ok"):
            result["online"] = True
            result["agent_status"] = data.get("data")
        else:
            result["error"] = data.get("error", "Unknown error")
    except http_requests.exceptions.ConnectionError:
        result["error"] = "Connection refused"
    except http_requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)

    return result


# ── CRUD Endpoints ───────────────────────────────────────────────────────

@bp.get("/api/servers")
def list_servers():
    """List all servers with live agent status (parallel fetch)."""
    servers = get_all_servers()
    if not servers:
        return jsonify({"ok": True, "data": []})

    results = []
    with ThreadPoolExecutor(max_workers=min(len(servers), 5)) as pool:
        futures = {pool.submit(_fetch_server_status, s): s for s in servers}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                s = futures[future]
                results.append({
                    "id": s["id"], "name": s["name"],
                    "display_name": s["display_name"], "ip": s["ip"],
                    "server_type": s["server_type"], "location": s["location"],
                    "provider": s["provider"], "status": s["status"],
                    "online": False, "agent_status": None, "error": str(e),
                })

    # Sort by original DB order
    order = {s["id"]: i for i, s in enumerate(servers)}
    results.sort(key=lambda r: order.get(r["id"], 999))

    return jsonify({"ok": True, "data": results})


@bp.post("/api/servers")
def add_server():
    """Register a new server (without provisioning)."""
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip().lower()
    display_name = (body.get("display_name") or "").strip()
    ip = (body.get("ip") or "").strip()
    server_type = (body.get("server_type") or "").strip()

    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if not ip:
        return jsonify({"ok": False, "error": "ip is required"}), 400
    if server_type not in ("vpn_exit", "dpi_bypass"):
        return jsonify({"ok": False, "error": "server_type must be vpn_exit or dpi_bypass"}), 400
    if not display_name:
        display_name = name.upper()

    from core.db import get_server_by_name
    if get_server_by_name(name):
        return jsonify({"ok": False, "error": "Server with this name already exists"}), 409

    data = {
        "name": name,
        "display_name": display_name,
        "ip": ip,
        "server_type": server_type,
        "location": (body.get("location") or "").strip(),
        "provider": (body.get("provider") or "").strip(),
        "status": "new",
    }

    # Encrypt root password if provided
    root_password = (body.get("root_password") or "").strip()
    if root_password:
        data["root_password_enc"] = encrypt_value(root_password)

    server_id = create_server(data)
    return jsonify({"ok": True, "data": {"id": server_id}})


@bp.get("/api/servers/<int:server_id>")
def get_server_detail(server_id: int):
    """Server detail with decrypted credentials."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    result = dict(server)

    # Decrypt credentials for display
    for enc_field, plain_field in [
        ("ss_password_enc", "ss_password"),
        ("agent_api_key_enc", "agent_api_key"),
        ("ssconf_token_enc", "ssconf_token"),
        ("speedtest_api_key_enc", "speedtest_api_key"),
    ]:
        enc_val = result.pop(enc_field, None)
        if enc_val:
            result[plain_field] = decrypt_value(enc_val) or "***decrypt error***"
        else:
            result[plain_field] = None

    # Remove root password from response (security)
    result.pop("root_password_enc", None)

    # Include recent operations
    result["operations"] = get_operations_by_server(server_id, limit=10)

    return jsonify({"ok": True, "data": result})


@bp.put("/api/servers/<int:server_id>")
def update_server_endpoint(server_id: int):
    """Update server metadata."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    body = request.get_json(force=True, silent=True) or {}
    updates = {}

    for field in ("name", "display_name", "ip", "location", "provider"):
        if field in body:
            updates[field] = body[field].strip() if isinstance(body[field], str) else body[field]

    if "server_type" in body and body["server_type"] in ("vpn_exit", "dpi_bypass"):
        updates["server_type"] = body["server_type"]

    if "install_adguard" in body:
        updates["install_adguard"] = 1 if body["install_adguard"] else 0

    # Encrypt root password if provided
    root_password = (body.get("root_password") or "").strip()
    if root_password:
        updates["root_password_enc"] = encrypt_value(root_password)

    if not updates:
        return jsonify({"ok": False, "error": "No valid fields to update"}), 400

    update_server(server_id, updates)
    return jsonify({"ok": True})


@bp.delete("/api/servers/<int:server_id>")
def delete_server_endpoint(server_id: int):
    """Remove a server."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    from core.inventory_writer import remove_host_vars
    remove_host_vars(server["name"])

    delete_server(server_id)

    # Regenerate hosts.yml without this server
    from core.inventory_writer import write_hosts_yml
    write_hosts_yml(get_all_servers())

    return jsonify({"ok": True})


# ── Agent Proxy Endpoints ────────────────────────────────────────────────

@bp.get("/api/servers/<int:server_id>/status")
def get_live_status(server_id: int):
    """Fetch live status from agent."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    result = _fetch_server_status(server)
    return jsonify({"ok": True, "data": result})


@bp.get("/api/servers/<int:server_id>/ss-key")
def get_ss_key(server_id: int):
    """Get SS key from agent."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404
    try:
        result = _proxy_request(server, "GET", "/api/ss-key")
        return jsonify(result)
    except http_requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "Cannot reach server"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@bp.post("/api/servers/<int:server_id>/restart")
def restart_services(server_id: int):
    """Restart services via agent."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    body = request.get_json(force=True, silent=True) or {}
    try:
        result = _proxy_request(server, "POST", "/api/restart", body)
        return jsonify(result)
    except http_requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "Cannot reach server"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@bp.get("/api/servers/<int:server_id>/dpi-args")
def get_dpi_args(server_id: int):
    """Get DPI args from agent (dpi_bypass only)."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404
    try:
        result = _proxy_request(server, "GET", "/api/dpi-args")
        return jsonify(result)
    except http_requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "Cannot reach server"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@bp.put("/api/servers/<int:server_id>/dpi-args")
def update_dpi_args(server_id: int):
    """Update DPI args via agent (dpi_bypass only)."""
    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    body = request.get_json(force=True, silent=True) or {}
    if not body.get("dpi_args"):
        return jsonify({"ok": False, "error": "dpi_args is required"}), 400

    try:
        result = _proxy_request(server, "PUT", "/api/dpi-args", body)
        return jsonify(result)
    except http_requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "Cannot reach server"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502
