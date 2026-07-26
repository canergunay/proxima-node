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
    get_admin,
    get_admin_by_username,
    get_admin_scope,
    get_all_admins,
    get_vpn_server,
    set_admin_scope,
    superadmin_count,
    update_admin,
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
        "scope": [] if admin["role"] == SUPERADMIN else get_admin_scope(admin["id"]),
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
    if password:
        if len(password) < MIN_PASSWORD_LEN:
            return jsonify({"ok": False, "error":
                            f"Password must be at least {MIN_PASSWORD_LEN} characters"}), 400
        updates["password_hash"] = hash_password(password)

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

    log.info(f"[ADMINS] Updated '{admin['username']}' ({', '.join(sorted(updates)) or 'scope'})")
    result = _public(get_admin(admin_id))
    if password:
        result["password"] = password
    return jsonify({"ok": True, "data": result})


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

    delete_admin(admin_id)
    log.info(f"[ADMINS] Deleted '{admin['username']}'")
    return jsonify({"ok": True, "data": {"message": f"Admin {admin['username']} deleted"}})
