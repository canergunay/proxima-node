"""Auth API — setup, login, me, password change."""

import logging

from flask import Blueprint, g, jsonify, request

from core.auth import (
    check_rate_limit,
    clear_login_failures,
    create_token,
    hash_password,
    record_login_failure,
    verify_password,
)
from core.db import admin_count, create_admin, get_admin_by_username, update_admin_password

log = logging.getLogger("adm.auth")
bp = Blueprint("auth", __name__)


@bp.get("/api/auth/me")
def me():
    """Check auth status. Works without auth to detect if setup is needed."""
    if admin_count() == 0:
        return jsonify({"ok": True, "data": {"auth_configured": False}})

    user_info = getattr(g, "user_info", None)
    if user_info:
        return jsonify({"ok": True, "data": {
            "auth_configured": True,
            "username": user_info["username"],
        }})

    return jsonify({"ok": False, "error": "Unauthorized"}), 401


@bp.post("/api/auth/setup")
def setup():
    """First-time admin creation. Only works if no admin exists."""
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or len(username) < 2:
        return jsonify({"ok": False, "error": "Username must be at least 2 characters"}), 400
    if not password or len(password) < 4:
        return jsonify({"ok": False, "error": "Password must be at least 4 characters"}), 400

    if admin_count() > 0:
        return jsonify({"ok": False, "error": "Admin account already exists"}), 409

    create_admin(username, hash_password(password))
    token = create_token(username)
    log.info(f"[AUTH] Initial setup: admin '{username}' created")
    return jsonify({"ok": True, "data": {"token": token}}), 201


@bp.post("/api/auth/login")
def login():
    if admin_count() == 0:
        return jsonify({"ok": False, "error": "Auth not configured — use setup"}), 400

    ip = request.remote_addr or "unknown"

    lockout = check_rate_limit(ip)
    if lockout:
        log.warning(f"[AUTH] Rate limited: {ip} ({lockout}s remaining)")
        return jsonify({"ok": False, "error": "Too many login attempts. Try again later.", "retry_after": lockout}), 429

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    admin = get_admin_by_username(username)
    if admin and verify_password(password, admin["password_hash"]):
        token = create_token(username)
        log.info(f"[AUTH] Login OK: '{username}' from {ip}")
        clear_login_failures(ip)
        return jsonify({"ok": True, "data": {"token": token}})

    log.warning(f"[AUTH] Login failed: '{username}' from {ip}")
    record_login_failure(ip)
    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@bp.put("/api/auth/password")
def change_password():
    body = request.get_json(silent=True) or {}
    current = body.get("current_password") or ""
    new_pass = body.get("new_password") or ""

    if not new_pass or len(new_pass) < 4:
        return jsonify({"ok": False, "error": "New password must be at least 4 characters"}), 400

    username = getattr(g, "user", None)
    if not username:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    admin = get_admin_by_username(username)
    if not admin:
        return jsonify({"ok": False, "error": "Admin not found"}), 404

    if not verify_password(current, admin["password_hash"]):
        return jsonify({"ok": False, "error": "Current password is incorrect"}), 401

    update_admin_password(admin["id"], hash_password(new_pass))
    log.info(f"[AUTH] Password changed: '{username}'")
    return jsonify({"ok": True, "data": {"message": "Password changed"}})
