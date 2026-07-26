"""Central VPN user management — ADM defines accounts, instances replicate them.

Each Proxima instance holds a read-only replica of these users in its own
`vpn_users` table. Every mutation here writes to the ADM database and then
immediately tries to push the affected rows (see core/vpn_user_sync.py). A
push that fails leaves the row `pending`/`error` rather than failing the
request: an unreachable site must not block editing the central record, and
the sync endpoints re-drive it once the site is back.

Passwords are set by the admin. Only the hash is stored; the plaintext is
echoed back in the response that set it — so the onboarding block can be
assembled — and never persisted. One is generated only when a caller omits
it entirely.
"""

import json
import logging
import re

from flask import Blueprint, jsonify, request

from core.auth import hash_password
from core.credential_gen import gen_vpn_user_password
from core.db import (
    create_vpn_user,
    delete_user_access,
    delete_vpn_user,
    get_all_user_access,
    get_all_vpn_users,
    get_access,
    get_sync_summary,
    get_user_access,
    get_vpn_server,
    get_vpn_user,
    get_vpn_user_by_username,
    mark_access_pending_delete,
    mark_all_access_pending,
    update_vpn_user,
    upsert_user_access,
)
from core.vpn_user_import import apply_import, build_preview
from core.vpn_user_sync import reconcile_passwords, sync_pending

log = logging.getLogger("adm.vpn_users")
bp = Blueprint("vpn_users", __name__)

USERNAME_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
MIN_PASSWORD_LEN = 8


# ── Helpers ──────────────────────────────────────────────────────────────

def _public_user(user: dict, access: list[dict]) -> dict:
    """Strip the hash and attach the server-access list."""
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "enabled": bool(user["enabled"]),
        "note": user["note"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
        "servers": [_public_access(a) for a in access],
    }


def _public_access(a: dict) -> dict:
    try:
        groups = json.loads(a.get("assigned_groups") or "[]")
    except (ValueError, TypeError):
        groups = []
    return {
        "vpn_server_id": a["vpn_server_id"],
        "server_name": a.get("server_name"),
        "server_display_name": a.get("server_display_name"),
        "remote_user_id": a.get("remote_user_id"),
        "enabled": bool(a["enabled"]),
        "lan_access": bool(a["lan_access"]),
        "max_peers": a["max_peers"],
        "bandwidth_quota": a["bandwidth_quota"],
        "speed_download": a["speed_download"],
        "speed_upload": a["speed_upload"],
        "assigned_groups": groups,
        "sync_status": a["sync_status"],
        "sync_error": a["sync_error"],
        "synced_at": a["synced_at"],
    }


def _push_now(user_id: int) -> dict:
    """Push a user's pending rows immediately (hybrid sync).

    Every mutation tries to reach the instances right away, so the admin sees
    the result while still looking at the change. A failure is not raised: the
    row stays pending/error and the UI surfaces it, because an unreachable
    site must not block editing the central record.
    """
    try:
        result = sync_pending(user_id=user_id)
    except Exception as e:  # noqa: BLE001 — reported, never fatal
        log.error(f"[VPN-USERS] Immediate sync failed for user {user_id}: {e}")
        return {"failed": [{"target": "sync", "error": str(e)}]}
    return result


def _parse_access_body(body: dict) -> tuple[dict | None, str | None]:
    """Validate the per-server limit fields. Returns (data, error)."""
    data: dict = {}

    for flag in ("enabled", "lan_access"):
        if flag in body:
            data[flag] = 1 if body[flag] else 0

    for field in ("max_peers", "bandwidth_quota"):
        if field in body:
            val = body[field]
            if val in (None, ""):
                data[field] = None
                continue
            try:
                data[field] = int(val)
            except (TypeError, ValueError):
                return None, f"Invalid {field}"

    for field in ("speed_download", "speed_upload"):
        if field in body:
            val = body[field]
            data[field] = str(val).strip() if val else None

    if "assigned_groups" in body:
        groups = body["assigned_groups"]
        if not isinstance(groups, list):
            return None, "assigned_groups must be a list"
        data["assigned_groups"] = json.dumps(groups)

    return data, None


# ── User CRUD ────────────────────────────────────────────────────────────

@bp.get("/api/vpn-users")
def list_users():
    """All central users with their server authorizations."""
    users = get_all_vpn_users()
    access_by_user: dict[int, list[dict]] = {}
    for a in get_all_user_access():
        access_by_user.setdefault(a["user_id"], []).append(a)

    return jsonify({"ok": True, "data": [
        _public_user(u, access_by_user.get(u["id"], [])) for u in users
    ]})


@bp.post("/api/vpn-users")
def add_user():
    """Create a user. Password is generated unless supplied, returned once."""
    body = request.get_json(silent=True) or {}

    username = (body.get("username") or "").strip().lower()
    if not username:
        return jsonify({"ok": False, "error": "username is required"}), 400
    if not USERNAME_RE.match(username):
        return jsonify({"ok": False, "error":
                        "username may contain only lowercase letters, digits, "
                        "'.', '_' and '-'"}), 400
    if get_vpn_user_by_username(username):
        return jsonify({"ok": False, "error":
                        f"User already exists: {username}"}), 409

    password = (body.get("password") or "").strip()
    if password and len(password) < MIN_PASSWORD_LEN:
        return jsonify({"ok": False, "error":
                        f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400
    if not password:
        password = gen_vpn_user_password()

    # Validate every server grant before writing anything — a failure halfway
    # through would otherwise leave a user created with partial access.
    grants: list[tuple[int, dict]] = []
    for entry in body.get("servers") or []:
        server_id = entry.get("vpn_server_id")
        if not server_id or not get_vpn_server(server_id):
            return jsonify({"ok": False, "error":
                            f"VPN server not found: {server_id}"}), 404
        data, err = _parse_access_body(entry)
        if err:
            return jsonify({"ok": False, "error": f"{err} (server {server_id})"}), 400
        grants.append((server_id, data))

    user_id = create_vpn_user({
        "username": username,
        "full_name": (body.get("full_name") or "").strip(),
        "password_hash": hash_password(password),
        "enabled": body.get("enabled", True),
        "note": (body.get("note") or "").strip(),
    })
    for server_id, data in grants:
        upsert_user_access(user_id, server_id, data)

    log.info(f"[VPN-USERS] Created central user '{username}' (id={user_id})")
    sync = _push_now(user_id)
    user = get_vpn_user(user_id)
    result = _public_user(user, get_user_access(user_id))
    result["password"] = password  # shown once, never stored in plaintext
    result["sync"] = sync
    return jsonify({"ok": True, "data": result}), 201


@bp.get("/api/vpn-users/<int:user_id>")
def get_user_detail(user_id: int):
    user = get_vpn_user(user_id)
    if not user:
        return jsonify({"ok": False, "error": "User not found"}), 404
    return jsonify({"ok": True, "data": _public_user(user, get_user_access(user_id))})


@bp.put("/api/vpn-users/<int:user_id>")
def edit_user(user_id: int):
    """Update identity fields. Any change here marks every access row pending."""
    user = get_vpn_user(user_id)
    if not user:
        return jsonify({"ok": False, "error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    updates: dict = {}
    new_password: str | None = None

    access = get_user_access(user_id)

    if "username" in body:
        username = (body["username"] or "").strip().lower()
        if not USERNAME_RE.match(username):
            return jsonify({"ok": False, "error": "Invalid username"}), 400
        if username != user["username"]:
            if get_vpn_user_by_username(username):
                return jsonify({"ok": False, "error":
                                f"User already exists: {username}"}), 409
            # Proxima cannot rename a vpn_user, and the VPN client stores the
            # username alongside its saved token — a rename after the account
            # exists on a server would silently break that login.
            pushed = [a["server_name"] for a in access
                      if a.get("remote_user_id") is not None]
            if pushed:
                return jsonify({"ok": False, "error":
                                "Cannot rename — the account already exists on: "
                                + ", ".join(pushed)
                                + ". Create a new user instead."}), 409
            updates["username"] = username

    if "full_name" in body:
        updates["full_name"] = (body["full_name"] or "").strip()
    if "note" in body:
        updates["note"] = (body["note"] or "").strip()
    if "enabled" in body:
        updates["enabled"] = 1 if body["enabled"] else 0

    if body.get("password"):
        new_password = str(body["password"]).strip()
        if len(new_password) < MIN_PASSWORD_LEN:
            return jsonify({"ok": False, "error":
                            f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400
        updates["password_hash"] = hash_password(new_password)

    if not updates:
        return jsonify({"ok": False, "error": "No fields to update"}), 400

    update_vpn_user(user_id, updates)

    # Only fields the Proxima instances actually replicate need a re-push.
    # full_name and note are ADM-side bookkeeping.
    if updates.keys() & {"password_hash", "enabled", "username"}:
        mark_all_access_pending(user_id)

    log.info(f"[VPN-USERS] Updated central user '{user['username']}' "
             f"({', '.join(sorted(updates))})")
    sync = _push_now(user_id)
    result = _public_user(get_vpn_user(user_id), get_user_access(user_id))
    if new_password:
        result["password"] = new_password
    result["sync"] = sync
    return jsonify({"ok": True, "data": result})


@bp.post("/api/vpn-users/<int:user_id>/password")
def set_password(user_id: int):
    """Set a new password. Generated only when none is supplied."""
    user = get_vpn_user(user_id)
    if not user:
        return jsonify({"ok": False, "error": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    password = (body.get("password") or "").strip()
    if password and len(password) < MIN_PASSWORD_LEN:
        return jsonify({"ok": False, "error":
                        f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400
    if not password:
        password = gen_vpn_user_password()

    update_vpn_user(user_id, {"password_hash": hash_password(password)})
    mark_all_access_pending(user_id)

    log.info(f"[VPN-USERS] Password changed for '{user['username']}'")
    sync = _push_now(user_id)
    return jsonify({"ok": True, "data": {"password": password, "sync": sync}})


@bp.delete("/api/vpn-users/<int:user_id>")
def remove_user(user_id: int):
    """Delete a user. Refused while the user is still authorized anywhere.

    Deleting here would cascade the access rows away and leave the remote
    accounts (and their peers) stranded on the Proxima instances. Revoke each
    server first, let the sync remove them, then delete.
    """
    user = get_vpn_user(user_id)
    if not user:
        return jsonify({"ok": False, "error": "User not found"}), 404

    access = get_user_access(user_id)
    if access:
        return jsonify({"ok": False, "error":
                        "Revoke server access first — still authorized on: "
                        + ", ".join(a["server_name"] for a in access)}), 409

    delete_vpn_user(user_id)
    log.info(f"[VPN-USERS] Deleted central user '{user['username']}'")
    return jsonify({"ok": True, "data": {
        "message": f"User {user['username']} deleted",
    }})


# ── Push to the Proxima instances ────────────────────────────────────────

@bp.get("/api/vpn-users/sync/status")
def sync_status():
    """How many access rows are waiting to be pushed, and what failed."""
    return jsonify({"ok": True, "data": get_sync_summary()})


@bp.post("/api/vpn-users/reconcile-passwords")
def reconcile_passwords_endpoint():
    """Carry self-service password changes to each user's other sites."""
    return jsonify({"ok": True, "data": reconcile_passwords()})


@bp.post("/api/vpn-users/sync")
def sync_all():
    """Reconcile every pending row. Optional body: {"vpn_server_id": N}."""
    body = request.get_json(silent=True) or {}
    vpn_server_id = body.get("vpn_server_id")
    if vpn_server_id is not None and not get_vpn_server(vpn_server_id):
        return jsonify({"ok": False, "error": "VPN server not found"}), 404
    return jsonify({"ok": True, "data": sync_pending(vpn_server_id=vpn_server_id)})


@bp.post("/api/vpn-users/<int:user_id>/sync")
def sync_one_user(user_id: int):
    """Reconcile the pending rows of a single user."""
    if not get_vpn_user(user_id):
        return jsonify({"ok": False, "error": "User not found"}), 404
    return jsonify({"ok": True, "data": sync_pending(user_id=user_id)})


# ── One-time import from the Proxima instances ───────────────────────────

@bp.get("/api/vpn-users/import/preview")
def import_preview():
    """What the import would do. Read-only — changes nothing."""
    return jsonify({"ok": True, "data": build_preview()})


@bp.post("/api/vpn-users/import")
def import_apply():
    """Import selected usernames as central users.

    Body: {"selections": [{"username": ..., "primary_server_id": ...}]}
    """
    body = request.get_json(silent=True) or {}
    selections = body.get("selections")
    if not isinstance(selections, list) or not selections:
        return jsonify({"ok": False, "error": "selections must be a non-empty list"}), 400

    return jsonify({"ok": True, "data": apply_import(selections)})


# ── Server authorization ─────────────────────────────────────────────────

@bp.put("/api/vpn-users/<int:user_id>/access/<int:vpn_server_id>")
def grant_access(user_id: int, vpn_server_id: int):
    """Authorize a user on a server, or update the per-server limits."""
    if not get_vpn_user(user_id):
        return jsonify({"ok": False, "error": "User not found"}), 404
    server = get_vpn_server(vpn_server_id)
    if not server:
        return jsonify({"ok": False, "error": "VPN server not found"}), 404

    data, err = _parse_access_body(request.get_json(silent=True) or {})
    if err:
        return jsonify({"ok": False, "error": err}), 400

    upsert_user_access(user_id, vpn_server_id, data)
    sync = _push_now(user_id)
    access = get_access(user_id, vpn_server_id)
    if not access:  # pushed and then removed (revoke raced) — nothing to show
        return jsonify({"ok": True, "data": {"sync": sync}})
    access["server_name"] = server["name"]
    access["server_display_name"] = server["display_name"]
    return jsonify({"ok": True, "data": {**_public_access(access), "sync": sync}})


@bp.delete("/api/vpn-users/<int:user_id>/access/<int:vpn_server_id>")
def revoke_access(user_id: int, vpn_server_id: int):
    """Flag authorization for removal.

    The row stays until the sync has deleted the remote account, so the
    revocation cannot be silently lost while the instance is unreachable.
    Unsynced grants (never pushed) are dropped immediately — there is
    nothing remote to clean up.

    The sync deletes the remote account together with its peers: a WireGuard
    peer keeps carrying traffic on its own keys after its owner is gone, so
    keeping them would leave the access revoked in name only. To suspend
    without destroying devices, set enabled=0 on the grant instead.
    """
    access = get_access(user_id, vpn_server_id)
    if not access:
        return jsonify({"ok": False, "error": "Access not found"}), 404

    if access.get("remote_user_id") is None:
        delete_user_access(user_id, vpn_server_id)
        return jsonify({"ok": True, "data": {
            "message": "Access removed", "pending_sync": False,
        }})

    mark_access_pending_delete(user_id, vpn_server_id)
    sync = _push_now(user_id)
    still_pending = get_access(user_id, vpn_server_id) is not None
    return jsonify({"ok": True, "data": {
        "message": "Access revoked — the remote account and its peers are removed",
        "pending_sync": still_pending,
        "deletes_peers": True,
        "remote_user_id": access["remote_user_id"],
        "sync": sync,
    }})
