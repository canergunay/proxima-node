"""Provisioning API — provision, decommission, rotate, update-agent, install-xray-reality."""

import logging

import requests as http_requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Blueprint, jsonify, request

from core.ansible_runner import current_operation_id, is_running, run_playbook
from core.auth import decrypt_value, encrypt_value
from core.credential_gen import (
    gen_agent_api_key,
    gen_node_id,
    gen_ss_password,
    gen_ssconf_token,
)
from core.db import (
    create_operation,
    get_server,
    update_server,
)
from core.inventory_writer import regenerate_for_server, regenerate_inventory

log = logging.getLogger("adm.provision")
bp = Blueprint("provision", __name__)


def _check_not_running():
    """Return error response if a playbook is already running."""
    if is_running():
        return jsonify({
            "ok": False,
            "error": "Another operation is already running",
            "current_op_id": current_operation_id(),
        }), 409
    return None


@bp.post("/api/provision")
def provision():
    """Start provisioning a server."""
    busy = _check_not_running()
    if busy:
        return busy

    body = request.get_json(force=True, silent=True) or {}
    server_id = body.get("server_id")

    if not server_id:
        return jsonify({"ok": False, "error": "server_id is required"}), 400

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] not in ("new", "error"):
        return jsonify({"ok": False, "error": f"Cannot provision server in '{server['status']}' status"}), 400

    # Accept root_password from request body if not already stored
    root_password = (body.get("root_password") or "").strip()
    if root_password:
        update_server(server_id, {"root_password_enc": encrypt_value(root_password)})
        server = get_server(server_id)

    if not server.get("root_password_enc"):
        return jsonify({"ok": False, "error": "Root password required for provisioning"}), 400

    # Generate credentials
    ss_password = gen_ss_password()
    agent_api_key = gen_agent_api_key()
    ssconf_token = gen_ssconf_token()
    node_id = gen_node_id(server["name"])

    updates = {
        "status": "provisioning",
        "ss_password_enc": encrypt_value(ss_password),
        "agent_api_key_enc": encrypt_value(agent_api_key),
        "ssconf_token_enc": encrypt_value(ssconf_token),
        "node_id": node_id,
    }

    update_server(server_id, updates)

    # Refresh server data
    server = get_server(server_id)

    # Write inventory
    regenerate_for_server(server, include_ssh_pass=True)

    # Choose playbook based on server type
    if server["server_type"] == "vpn_exit":
        playbook = "setup-vpn-exit.yml"
    else:
        playbook = "setup-dpi-bypass.yml"

    # Create operation
    op_id = create_operation(server_id, "provision", playbook)

    # Completion callback
    def on_complete(success: bool, op_id: int):
        if success:
            update_server(server_id, {"status": "active"})
            # Regenerate host_vars WITHOUT ssh password
            srv = get_server(server_id)
            if srv:
                regenerate_for_server(srv, include_ssh_pass=False)
            log.info(f"[PROVISION] Server {server['name']} provisioned successfully")
        else:
            update_server(server_id, {"status": "error"})
            log.error(f"[PROVISION] Server {server['name']} provisioning failed")

    run_playbook(op_id, playbook, limit=server["name"], on_complete=on_complete)

    return jsonify({"ok": True, "data": {"operation_id": op_id}})


@bp.post("/api/provision/<int:server_id>/decommission")
def decommission(server_id: int):
    """Decommission a server."""
    busy = _check_not_running()
    if busy:
        return busy

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] not in ("active", "error"):
        return jsonify({"ok": False, "error": f"Cannot decommission server in '{server['status']}' status"}), 400

    playbook = "decommission.yml"
    op_id = create_operation(server_id, "decommission", playbook)

    update_server(server_id, {"status": "provisioning"})

    def on_complete(success: bool, op_id: int):
        if success:
            update_server(server_id, {"status": "decommissioned"})
            from core.inventory_writer import remove_host_vars
            remove_host_vars(server["name"])
            regenerate_inventory()
            log.info(f"[PROVISION] Server {server['name']} decommissioned")
        else:
            update_server(server_id, {"status": "error"})
            log.error(f"[PROVISION] Server {server['name']} decommission failed")

    # Bypass vars_prompt with -e
    run_playbook(
        op_id, playbook,
        limit=server["name"],
        extra_vars={"confirm_decommission": server["name"]},
        on_complete=on_complete,
    )

    return jsonify({"ok": True, "data": {"operation_id": op_id}})


@bp.post("/api/provision/<int:server_id>/rotate")
def rotate_credentials(server_id: int):
    """Rotate credentials on a server."""
    busy = _check_not_running()
    if busy:
        return busy

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] != "active":
        return jsonify({"ok": False, "error": "Server must be active to rotate credentials"}), 400

    playbook = "rotate-credentials.yml"
    op_id = create_operation(server_id, "rotate", playbook)

    def on_complete(success: bool, op_id: int):
        if success:
            # After rotation, the playbook generates new credentials on the server.
            # We need to update our DB with whatever the playbook generated.
            # For now, we mark as active and the user can check via agent.
            log.info(f"[PROVISION] Credentials rotated on {server['name']}")
        else:
            log.error(f"[PROVISION] Credential rotation failed on {server['name']}")

    # Bypass vars_prompt
    run_playbook(
        op_id, playbook,
        limit=server["name"],
        extra_vars={"confirm_rotate": "yes"},
        on_complete=on_complete,
    )

    return jsonify({"ok": True, "data": {"operation_id": op_id}})


@bp.post("/api/provision/<int:server_id>/update-agent")
def update_agent(server_id: int):
    """Update proxima-agent on a server."""
    busy = _check_not_running()
    if busy:
        return busy

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] != "active":
        return jsonify({"ok": False, "error": "Server must be active to update agent"}), 400

    playbook = "update-agent.yml"
    op_id = create_operation(server_id, "update-agent", playbook)

    def on_complete(success: bool, op_id: int):
        if success:
            log.info(f"[PROVISION] Agent updated on {server['name']}")
        else:
            log.error(f"[PROVISION] Agent update failed on {server['name']}")

    run_playbook(op_id, playbook, limit=server["name"], on_complete=on_complete)

    return jsonify({"ok": True, "data": {"operation_id": op_id}})


@bp.post("/api/provision/<int:server_id>/install-agent")
def install_agent(server_id: int):
    """Deploy proxima-agent to a server that doesn't have it yet."""
    busy = _check_not_running()
    if busy:
        return busy

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] != "active":
        return jsonify({"ok": False, "error": "Server must be active to install agent"}), 400

    # Regenerate inventory so host_vars have the correct credentials
    regenerate_for_server(server)

    playbook = "migrate-agent.yml"
    op_id = create_operation(server_id, "install-agent", playbook)

    def on_complete(success: bool, op_id: int):
        if success:
            log.info(f"[PROVISION] Agent installed on {server['name']}")
        else:
            log.error(f"[PROVISION] Agent install failed on {server['name']}")

    run_playbook(op_id, playbook, limit=server["name"], on_complete=on_complete)

    return jsonify({"ok": True, "data": {"operation_id": op_id}})


def _fetch_vless_keys(server: dict) -> dict | None:
    """Fetch VLESS Reality keys from agent and return parsed data."""
    url = f"https://{server['ip']}:{server.get('agent_port', 5051)}/api/vless-key"
    headers = {}
    enc_key = server.get("agent_api_key_enc")
    if enc_key:
        api_key = decrypt_value(enc_key)
        if api_key:
            headers["X-API-Key"] = api_key
    try:
        resp = http_requests.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok") and data.get("data"):
            return data["data"]
    except Exception as e:
        log.warning(f"Failed to fetch VLESS keys: {e}")
    return None


@bp.post("/api/provision/<int:server_id>/install-xray-reality")
def install_xray_reality(server_id: int):
    """Install Xray VLESS Reality on a VPN exit server."""
    busy = _check_not_running()
    if busy:
        return busy

    server = get_server(server_id)
    if not server:
        return jsonify({"ok": False, "error": "Server not found"}), 404

    if server["status"] != "active":
        return jsonify({"ok": False, "error": "Server must be active"}), 400

    if server["server_type"] != "vpn_exit":
        return jsonify({"ok": False, "error": "VLESS Reality is only for vpn_exit servers"}), 400

    # Regenerate inventory so host_vars are current
    regenerate_for_server(server)

    playbook = "install-xray-reality.yml"
    op_id = create_operation(server_id, "install-xray-reality", playbook)

    def on_complete(success: bool, op_id: int):
        if success:
            # Fetch VLESS keys from agent and store in DB
            srv = get_server(server_id)
            if srv:
                vless_data = _fetch_vless_keys(srv)
                if vless_data:
                    update_server(server_id, {
                        "vless_uuid": vless_data.get("vless_uuid"),
                        "vless_public_key": vless_data.get("public_key"),
                        "vless_short_id": vless_data.get("short_id"),
                        "vless_port": vless_data.get("port", 8443),
                    })
                    log.info(f"[PROVISION] VLESS keys saved for {srv['name']}")
                else:
                    log.warning(f"[PROVISION] VLESS installed but could not fetch keys from {srv['name']}")
            log.info(f"[PROVISION] Xray Reality installed on {server['name']}")
        else:
            log.error(f"[PROVISION] Xray Reality install failed on {server['name']}")

    run_playbook(op_id, playbook, limit=server["name"], on_complete=on_complete)

    return jsonify({"ok": True, "data": {"operation_id": op_id}})
