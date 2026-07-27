"""ADM operator accounts — superadmin only.

Two roles. A `superadmin` may do anything, including managing these accounts.
An `admin` may only manage VPN users on the servers in their scope; every
other endpoint refuses them (see the allowlist in app.py).
"""

import logging

from flask import Blueprint, g, jsonify, request

from core.auth import hash_password
from core.authz import ADMIN, ROLES, SUPERADMIN, superadmin_only
from core.credential_gen import gen_vpn_user_password
from core.db import (
    create_admin,
    delete_admin,
    delete_admin_access,
    get_admin,
    get_admin_access,
    get_admin_by_username,
    get_admin_scope,
    get_all_admins,
    get_vpn_server,
    grant_admin_access,
    mark_admin_access_pending_delete,
    set_admin_scope,
    superadmin_count,
    update_admin,
    update_admin_password,
)

log = logging.getLogger("adm.admins")
bp = Blueprint("admins", __name__)

MIN_PASSWORD_LEN = 8


def _public(admin: dict) -> dict:
    return {
        "id": admin["id"],
        "username": admin["username"],
        "role": admin["role"],
        "enabled": bool(admin["enabled"]),
        "created_at": admin["created_at"],
        # Whose users they may edit here. Not the same as `access`, which is
        # whether they can sign into a site's own panel.
        "scope": [] if admin["role"] == SUPERADMIN else get_admin_scope(admin["id"]),
        "access": [
            {
                "vpn_server_id": a["vpn_server_id"],
                "sync_status": a["sync_status"],
                "sync_error": a["sync_error"],
                "synced_at": a["synced_at"],
            }
            for a in get_admin_access(admin["id"])
        ],
    }


def _validate_scope(role: str, scope) -> tuple[list[int] | None, str | None]:
    """A scoped admin needs servers; a superadmin must not carry a scope."""
    if role == SUPERADMIN:
        return [], None
    if not isinstance(scope, list) or not scope:
        return None, "A scoped admin needs at least one server"
    ids = []
    for sid in scope:
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return None, f"Invalid server id: {sid}"
        if not get_vpn_server(sid):
            return None, f"VPN server not found: {sid}"
        ids.append(sid)
    return ids, None


@bp.get("/api/admins")
@superadmin_only
def list_admins():
    return jsonify({"ok": True, "data": [_public(a) for a in get_all_admins()]})


@bp.post("/api/admins")
@superadmin_only
def add_admin():
    body = request.get_json(silent=True) or {}

    username = (body.get("username") or "").strip().lower()
    if len(username) < 2:
        return jsonify({"ok": False, "error": "Username must be at least 2 characters"}), 400
    if get_admin_by_username(username):
        return jsonify({"ok": False, "error": f"Admin already exists: {username}"}), 409

    role = body.get("role") or ADMIN
    if role not in ROLES:
        return jsonify({"ok": False, "error": f"Unknown role: {role}"}), 400

    scope, err = _validate_scope(role, body.get("scope"))
    if err:
        return jsonify({"ok": False, "error": err}), 400

    password = (body.get("password") or "").strip()
    if password and len(password) < MIN_PASSWORD_LEN:
        return jsonify({"ok": False, "error":
                        f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400
    if not password:
        password = gen_vpn_user_password()

    admin_id = create_admin(username, hash_password(password), role=role)
    set_admin_scope(admin_id, scope)

    log.info(f"[ADMINS] Created {role} '{username}' (scope={scope})")
    result = _public(get_admin(admin_id))
    result["password"] = password  # shown once
    return jsonify({"ok": True, "data": result}), 201


@bp.put("/api/admins/<int:admin_id>")
@superadmin_only
def edit_admin(admin_id: int):
    admin = get_admin(admin_id)
    if not admin:
        return jsonify({"ok": False, "error": "Admin not found"}), 404

    body = request.get_json(silent=True) or {}
    updates: dict = {}
    role = admin["role"]

    if "role" in body:
        role = body["role"]
        if role not in ROLES:
            return jsonify({"ok": False, "error": f"Unknown role: {role}"}), 400
        updates["role"] = role

    if "enabled" in body:
        updates["enabled"] = 1 if body["enabled"] else 0

    password = (body.get("password") or "").strip()
    if password and len(password) < MIN_PASSWORD_LEN:
        return jsonify({"ok": False, "error":
                        f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400

    # Losing the last superadmin would leave nobody able to manage servers,
    # provisioning or these accounts — including this one.
    demoting = updates.get("role") == ADMIN and admin["role"] == SUPERADMIN
    disabling = updates.get("enabled") == 0 and admin["role"] == SUPERADMIN
    if (demoting or disabling) and superadmin_count(exclude_id=admin_id) == 0:
        return jsonify({"ok": False, "error":
                        "This is the last superadmin"}), 409

    if "scope" in body or "role" in body:
        scope, err = _validate_scope(role, body.get("scope", get_admin_scope(admin_id)))
        if err:
            return jsonify({"ok": False, "error": err}), 400
        set_admin_scope(admin_id, scope)

    if updates:
        update_admin(admin_id, updates)

    # Through its own helper, so the sites this operator signs into are queued
    # for the new password. Writing the hash with the rest of the updates
    # would change it here and leave every panel on the old one.
    if password:
        update_admin_password(admin_id, hash_password(password))
        _push_now(admin_id)

    log.info(f"[ADMINS] Updated '{admin['username']}' "
             f"({', '.join(sorted(updates) + (['password'] if password else [])) or 'scope'})")
    result = _public(get_admin(admin_id))
    if password:
        result["password"] = password
    return jsonify({"ok": True, "data": result})


def _push_now(admin_id: int) -> dict:
    """Flush this operator's pending panel grants. Never fatal to the caller.

    A site being unreachable must not fail the edit that was already made —
    the row stays pending and the next run retries it.
    """
    from core.admin_sync import sync_pending
    try:
        return sync_pending(admin_id=admin_id)
    except Exception as e:  # noqa: BLE001
        log.warning(f"[ADMINS] Panel access push failed for admin {admin_id}: {e}")
        return {"granted": [], "removed": [], "failed": [{"error": str(e)}]}


@bp.put("/api/admins/<int:admin_id>/access")
@superadmin_only
def set_panel_access(admin_id: int):
    """Set which site panels this operator can sign into.

    The body carries the servers they should end up with; anything missing
    from it is revoked. Grants and revocations are queued and pushed
    immediately, and the response reports what each site said.
    """
    admin = get_admin(admin_id)
    if not admin:
        return jsonify({"ok": False, "error": "Admin not found"}), 404

    body = request.get_json(silent=True) or {}
    wanted_raw = body.get("vpn_server_ids")
    if not isinstance(wanted_raw, list):
        return jsonify({"ok": False, "error": "vpn_server_ids must be a list"}), 400

    wanted: set[int] = set()
    for sid in wanted_raw:
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": f"Invalid server id: {sid}"}), 400
        if not get_vpn_server(sid):
            return jsonify({"ok": False, "error": f"VPN server not found: {sid}"}), 404
        wanted.add(sid)

    current = {a["vpn_server_id"]: a for a in get_admin_access(admin_id)}

    for sid in wanted:
        # Re-granting something already queued for removal has to clear that
        # instruction, or the push would delete what was just asked for.
        if sid not in current or current[sid]["sync_status"] == "pending_delete":
            grant_admin_access(admin_id, sid)

    for sid, row in current.items():
        if sid in wanted:
            continue
        if row["sync_status"] == "pending":
            # Never reached the site, so there is nothing to revoke there.
            delete_admin_access(admin_id, sid)
        else:
            mark_admin_access_pending_delete(admin_id, sid)

    result = _push_now(admin_id)
    log.info(f"[ADMINS] Panel access for '{admin['username']}': "
             f"granted={len(result['granted'])} removed={len(result['removed'])} "
             f"failed={len(result['failed'])}")
    return jsonify({"ok": True, "data": {"admin": _public(get_admin(admin_id)),
                                         "sync": result}})


@bp.post("/api/admins/sync")
@superadmin_only
def sync_panel_access():
    """Retry every queued grant and revocation."""
    from core.admin_sync import sync_pending
    return jsonify({"ok": True, "data": sync_pending()})


@bp.delete("/api/admins/<int:admin_id>")
@superadmin_only
def remove_admin(admin_id: int):
    admin = get_admin(admin_id)
    if not admin:
        return jsonify({"ok": False, "error": "Admin not found"}), 404

    if admin["username"] == g.admin["username"]:
        return jsonify({"ok": False, "error": "You cannot delete your own account"}), 409

    if admin["role"] == SUPERADMIN and superadmin_count(exclude_id=admin_id) == 0:
        return jsonify({"ok": False, "error": "This is the last superadmin"}), 409

    # Their panel accounts have to come down first. The access rows cascade
    # away with the admin row, so deleting here without revoking would leave
    # working logins on every site and no record that they exist.
    for row in get_admin_access(admin_id):
        if row["sync_status"] == "pending":
            delete_admin_access(admin_id, row["vpn_server_id"])
        else:
            mark_admin_access_pending_delete(admin_id, row["vpn_server_id"])

    result = _push_now(admin_id)
    if result["failed"] and not request.args.get("force"):
        return jsonify({"ok": False, "error":
                        "Could not remove this operator's panel account from "
                        + ", ".join(sorted({f.get("target", "?").split("@")[-1]
                                            for f in result["failed"]}))
                        + ". Deleting them here would leave those logins working. "
                          "Retry, or delete anyway with force=true.",
                        "sync": result}), 409

    delete_admin(admin_id)
    log.info(f"[ADMINS] Deleted '{admin['username']}' "
             f"(panel accounts removed: {len(result['removed'])})")
    return jsonify({"ok": True, "data": {"message": f"Admin {admin['username']} deleted",
                                         "sync": result}})
