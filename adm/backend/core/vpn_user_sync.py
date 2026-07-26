"""Push central VPN users down to the Proxima instances.

Every access row marked `pending` is created or updated on its instance, and
every row marked `pending_delete` has its remote account removed.

Ownership is split rather than exclusive. ADM decides who exists, where they
are authorized, and the limits; the user owns their own devices and may
change their own password from the client. So the push is authoritative for
every field *except* the password, which it carries only when ADM set it more
recently than the last push delivered one — see _password_is_ours.

Revocation deletes the remote account **with its peers**. A WireGuard peer
keeps working on its own keys regardless of whether the owning account still
exists — leaving the peers behind would mean "revoked" access that still
carries traffic. Use disable (enabled=0) when the intent is to suspend an
account without destroying its devices.
"""

import json
import logging

from core.db import (
    delete_user_access,
    get_all_vpn_servers,
    get_pending_access,
    mark_access_error,
    mark_access_synced,
)
from core.proxima_client import call

log = logging.getLogger("adm.vpn_user_sync")


def _remote_payload(row: dict) -> dict:
    """Fields a Proxima instance stores for a user."""
    try:
        groups = json.loads(row.get("assigned_groups") or "[]")
    except (ValueError, TypeError):
        groups = []
    return {
        "max_peers": row["max_peers"],
        "bandwidth_quota": row["bandwidth_quota"],
        "speed_download": row["speed_download"],
        "speed_upload": row["speed_upload"],
        "assigned_groups": groups,
        "lan_access": bool(row["lan_access"]),
    }


def _effective_enabled(row: dict) -> bool:
    """A user is active on a server only if both the account and the grant are."""
    return bool(row["user_enabled"]) and bool(row["enabled"])


def _password_is_ours(row: dict) -> bool:
    """Should this push carry the password?

    Only when ADM set it more recently than the last push that delivered it.
    Users may change their own password from the client, and a push triggered
    by something unrelated — a peer limit, a LAN toggle — must not silently
    put the old one back. An admin who sets a new password bumps the stamp
    and wins on the next push, which is the intended precedence.
    """
    changed = row.get("password_changed_at") or 0
    synced = row.get("password_synced_at") or 0
    return changed > synced


def _find_remote_by_username(server: dict, username: str) -> int | None:
    """Look up an existing remote account by username."""
    data, error = call(server, "GET", "/api/vpn/users", timeout=20)
    if error or not isinstance(data, list):
        return None
    for user in data:
        if user.get("username") == username:
            return user.get("id")
    return None


def _push_delete(server: dict, row: dict) -> tuple[bool, str | None, str]:
    remote_id = row.get("remote_user_id")
    if remote_id is None:
        delete_user_access(row["user_id"], row["vpn_server_id"])
        return True, None, "removed"

    _, error = call(
        server, "DELETE", f"/api/vpn/users/{remote_id}?cascade=true", timeout=30
    )
    # Already gone remotely is the desired end state, not a failure.
    if error and "not found" not in error.lower():
        return False, error, "removed"

    delete_user_access(row["user_id"], row["vpn_server_id"])
    log.info(f"[SYNC] Removed '{row['username']}' from {row['server_name']} "
             f"(remote id {remote_id}, peers deleted)")
    return True, None, "removed"


def _push_create(server: dict, row: dict) -> tuple[bool, str | None, str]:
    body = {"username": row["username"], "password_hash": row["password_hash"]}
    body.update(_remote_payload(row))

    data, error = call(server, "POST", "/api/vpn/users", body=body, timeout=30)

    if error and "already exists" in error.lower():
        # Adopt the existing account rather than failing — this happens when a
        # previous run created it but could not record the id. Report it as an
        # adoption, not a creation: nothing new appeared on the instance.
        remote_id = _find_remote_by_username(server, row["username"])
        if remote_id is None:
            return False, "Remote user exists but could not be located", "adopted"
        ok, err, _ = _push_update(server, {**row, "remote_user_id": remote_id})
        return ok, err, "adopted"

    if error:
        return False, error, "created"

    remote_id = (data or {}).get("id")
    if remote_id is None:
        return False, "Create succeeded but returned no id", "created"

    # Proxima creates users enabled; suspend right away when the grant says so.
    if not _effective_enabled(row):
        _, err = call(server, "PUT", f"/api/vpn/users/{remote_id}",
                      body={"enabled": False}, timeout=30)
        if err:
            return False, f"Created but could not disable: {err}", "created"

    mark_access_synced(row["id"], remote_user_id=remote_id, password_pushed=True)
    log.info(f"[SYNC] Created '{row['username']}' on {row['server_name']} "
             f"(remote id {remote_id})")
    return True, None, "created"


def _push_update(server: dict, row: dict) -> tuple[bool, str | None, str]:
    remote_id = row["remote_user_id"]
    send_password = _password_is_ours(row)
    body = {"enabled": _effective_enabled(row)}
    if send_password:
        body["password_hash"] = row["password_hash"]
    body.update(_remote_payload(row))

    _, error = call(server, "PUT", f"/api/vpn/users/{remote_id}", body=body, timeout=30)

    if error and "not found" in error.lower():
        # Deleted on the instance behind ADM's back — recreate it.
        log.warning(f"[SYNC] '{row['username']}' missing on {row['server_name']}, "
                    "recreating")
        ok, err, _ = _push_create(server, {**row, "remote_user_id": None})
        return ok, err, "recreated"

    if error:
        return False, error, "updated"

    mark_access_synced(row["id"], remote_user_id=remote_id,
                       password_pushed=send_password)
    log.info(f"[SYNC] Updated '{row['username']}' on {row['server_name']}"
             + ("" if send_password else " (password left as-is)"))
    return True, None, "updated"


def sync_pending(vpn_server_id: int | None = None,
                 user_id: int | None = None) -> dict:
    """Reconcile every pending row, optionally scoped to a server or user."""
    rows = get_pending_access(vpn_server_id)
    if user_id is not None:
        rows = [r for r in rows if r["user_id"] == user_id]

    servers = {s["id"]: s for s in get_all_vpn_servers()}

    # Keyed by what actually happened on the instance, not by what was
    # attempted — an adoption or a recreate must not be reported as a create.
    done: dict[str, list[str]] = {
        "created": [], "adopted": [], "updated": [], "recreated": [], "removed": [],
    }
    failed: list[dict] = []

    for row in rows:
        server = servers.get(row["vpn_server_id"])
        label = f"{row['username']}@{row['server_name']}"

        if not server:
            mark_access_error(row["id"], "VPN server missing")
            failed.append({"target": label, "error": "VPN server missing"})
            continue

        if row["sync_status"] == "pending_delete":
            ok, error, action = _push_delete(server, row)
        elif row.get("remote_user_id") is None:
            ok, error, action = _push_create(server, row)
        else:
            ok, error, action = _push_update(server, row)

        if ok:
            done[action].append(label)
        else:
            mark_access_error(row["id"], error or "Unknown error")
            failed.append({"target": label, "error": error, "action": action})
            log.warning(f"[SYNC] Failed {label} ({action}): {error}")

    log.info("[SYNC] " + " ".join(f"{k}={len(v)}" for k, v in done.items())
             + f" failed={len(failed)}")

    return {**done, "failed": failed}
