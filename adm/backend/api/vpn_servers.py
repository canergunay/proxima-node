"""VPN server management API — CRUD + generic Proxima proxy."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as http_requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Blueprint, jsonify, request

from core.auth import decrypt_value, encrypt_value
from core.db import (
    create_vpn_server,
    delete_vpn_server,
    get_all_vpn_servers,
    get_vpn_server,
    update_vpn_server,
)

log = logging.getLogger("adm.vpn_servers")
bp = Blueprint("vpn_servers", __name__)


# ── Proxima proxy helpers ────────────────────────────────────────────────

def _proxima_headers(server: dict) -> dict:
    """Build auth headers for a Proxima instance."""
    headers = {}
    enc_token = server.get("api_token_enc")
    if enc_token:
        token = decrypt_value(enc_token)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def _proxima_request(server: dict, method: str, path: str,
                     body: dict | None = None, timeout: int = 15) -> http_requests.Response:
    """Forward an HTTP request to a Proxima instance. Returns raw Response."""
    base_url = server["url"].rstrip("/")
    url = f"{base_url}{path}"
    headers = _proxima_headers(server)

    if method == "GET":
        return http_requests.get(url, headers=headers, timeout=timeout, verify=False)
    elif method == "POST":
        return http_requests.post(url, json=body, headers=headers, timeout=timeout, verify=False)
    elif method == "PUT":
        return http_requests.put(url, json=body, headers=headers, timeout=timeout, verify=False)
    elif method == "DELETE":
        return http_requests.delete(url, headers=headers, timeout=timeout, verify=False)
    else:
        raise ValueError(f"Unsupported method: {method}")


def _fetch_vpn_server_status(server: dict) -> dict:
    """Fetch live status from a single Proxima instance."""
    result = {
        "id": server["id"],
        "name": server["name"],
        "display_name": server["display_name"],
        "url": server["url"],
        "has_token": bool(server.get("api_token_enc")),
        "online": False,
        "proxima_status": None,
        "error": None,
    }

    if not server.get("api_token_enc"):
        result["error"] = "No API token configured"
        return result

    try:
        resp = _proxima_request(server, "GET", "/api/status", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            result["online"] = True
            result["proxima_status"] = data.get("data")
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

@bp.get("/api/vpn-servers")
def list_vpn_servers():
    """List all VPN servers with live Proxima status (parallel fetch)."""
    servers = get_all_vpn_servers()
    if not servers:
        return jsonify({"ok": True, "data": []})

    results = []
    with ThreadPoolExecutor(max_workers=min(len(servers), 5)) as pool:
        futures = {pool.submit(_fetch_vpn_server_status, s): s for s in servers}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                s = futures[future]
                results.append({
                    "id": s["id"], "name": s["name"],
                    "display_name": s["display_name"], "url": s["url"],
                    "has_token": bool(s.get("api_token_enc")),
                    "online": False, "proxima_status": None, "error": str(e),
                })

    # Sort by original DB order
    order = {s["id"]: i for i, s in enumerate(servers)}
    results.sort(key=lambda r: order.get(r["id"], 999))

    return jsonify({"ok": True, "data": results})


@bp.post("/api/vpn-servers")
def add_vpn_server():
    """Register a new VPN server (Proxima instance)."""
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip().lower()
    display_name = (body.get("display_name") or "").strip()
    url = (body.get("url") or "").strip().rstrip("/")

    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if not url:
        return jsonify({"ok": False, "error": "url is required"}), 400
    if not display_name:
        display_name = name.upper()

    data = {
        "name": name,
        "display_name": display_name,
        "url": url,
    }

    api_token = (body.get("api_token") or "").strip()
    if api_token:
        data["api_token_enc"] = encrypt_value(api_token)

    try:
        server_id = create_vpn_server(data)
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"ok": False, "error": "VPN server with this name already exists"}), 409
        raise

    return jsonify({"ok": True, "data": {"id": server_id}})


@bp.get("/api/vpn-servers/<int:vpn_server_id>")
def get_vpn_server_detail(vpn_server_id: int):
    """VPN server detail (token not exposed, just has_token boolean)."""
    server = get_vpn_server(vpn_server_id)
    if not server:
        return jsonify({"ok": False, "error": "VPN server not found"}), 404

    result = {
        "id": server["id"],
        "name": server["name"],
        "display_name": server["display_name"],
        "url": server["url"],
        "has_token": bool(server.get("api_token_enc")),
        "created_at": server["created_at"],
        "updated_at": server["updated_at"],
    }

    return jsonify({"ok": True, "data": result})


@bp.put("/api/vpn-servers/<int:vpn_server_id>")
def update_vpn_server_endpoint(vpn_server_id: int):
    """Update VPN server metadata or token."""
    server = get_vpn_server(vpn_server_id)
    if not server:
        return jsonify({"ok": False, "error": "VPN server not found"}), 404

    body = request.get_json(force=True, silent=True) or {}
    updates = {}

    for field in ("name", "display_name", "url"):
        if field in body:
            val = body[field]
            updates[field] = val.strip() if isinstance(val, str) else val

    if "url" in updates:
        updates["url"] = updates["url"].rstrip("/")

    api_token = (body.get("api_token") or "").strip()
    if api_token:
        updates["api_token_enc"] = encrypt_value(api_token)

    if not updates:
        return jsonify({"ok": False, "error": "No valid fields to update"}), 400

    update_vpn_server(vpn_server_id, updates)
    return jsonify({"ok": True})


@bp.delete("/api/vpn-servers/<int:vpn_server_id>")
def delete_vpn_server_endpoint(vpn_server_id: int):
    """Remove a VPN server."""
    server = get_vpn_server(vpn_server_id)
    if not server:
        return jsonify({"ok": False, "error": "VPN server not found"}), 404

    delete_vpn_server(vpn_server_id)
    return jsonify({"ok": True})


# ── Generic Proxima Proxy ────────────────────────────────────────────────

@bp.route("/api/vpn-servers/<int:vpn_server_id>/proxima/<path:subpath>",
          methods=["GET", "POST", "PUT", "DELETE"])
def proxy_to_proxima(vpn_server_id: int, subpath: str):
    """Forward any request to the Proxima instance's API."""
    server = get_vpn_server(vpn_server_id)
    if not server:
        return jsonify({"ok": False, "error": "VPN server not found"}), 404

    if not server.get("api_token_enc"):
        return jsonify({"ok": False, "error": "No API token configured"}), 400

    method = request.method
    body = None
    if method in ("POST", "PUT"):
        body = request.get_json(force=True, silent=True)

    try:
        resp = _proxima_request(server, method, f"/api/{subpath}", body=body, timeout=30)
        # Pass through the Proxima response as-is
        return (resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except http_requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "Cannot reach Proxima instance"}), 502
    except http_requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "Proxima request timed out"}), 504
    except Exception as e:
        log.error(f"Proxima proxy error for {server['name']}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 502
