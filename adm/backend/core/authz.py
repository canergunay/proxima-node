"""Who may do what.

Two roles. A `superadmin` may do anything. An `admin` is limited to managing
VPN users on the servers in their scope, and nothing else — no provisioning,
no server registration, no alert config, no other admins.

The scope guard is deliberately strict about the *global* fields of a user.
An account exists once and its password and enabled flag apply everywhere,
so letting a site admin reset a password for someone who also belongs to a
site they cannot see would reach outside their scope. Those actions are
allowed only when every server the user belongs to is one they administer.
"""

from functools import wraps

from flask import g, jsonify

from core.db import get_admin_scope, get_user_access

SUPERADMIN = "superadmin"
ADMIN = "admin"
ROLES = (SUPERADMIN, ADMIN)


def current_admin() -> dict | None:
    return getattr(g, "admin", None)


def is_superadmin() -> bool:
    admin = current_admin()
    return bool(admin and admin["role"] == SUPERADMIN)


def scoped_server_ids() -> list[int] | None:
    """Servers the caller may manage users on. None means "all of them"."""
    if is_superadmin():
        return None
    admin = current_admin()
    return get_admin_scope(admin["id"]) if admin else []


def may_manage_server(vpn_server_id: int) -> bool:
    allowed = scoped_server_ids()
    return allowed is None or vpn_server_id in allowed


def may_manage_user(user_id: int) -> bool:
    """True when every server this user belongs to is in the caller's scope.

    A user with no access rows yet is fair game — they are not visible on any
    server the caller cannot see.
    """
    allowed = scoped_server_ids()
    if allowed is None:
        return True
    return all(a["vpn_server_id"] in allowed for a in get_user_access(user_id))


def forbidden(message: str = "Not permitted for this account"):
    return jsonify({"ok": False, "error": message}), 403


def superadmin_only(fn):
    """Guard for everything that is not per-server user management."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_superadmin():
            return forbidden("Superadmin only")
        return fn(*args, **kwargs)
    return wrapper
