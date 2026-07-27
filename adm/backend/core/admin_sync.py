"""Push panel admin accounts to the sites an operator administers.

An operator has one password. It signs them into ADM and into the panel of
every site they hold an account on. ADM stores only the hash and pushes that,
so the credential is shared without ADM ever being able to read it — the same
arrangement already used for VPN users.

Authentication itself stays on each box. A site whose ADM is unreachable
still lets its admins in; only changes wait.
"""

import logging

from core.db import (
    get_all_vpn_servers,
    get_pending_admin_access,
    mark_admin_access_error,
    mark_admin_access_synced,
    delete_admin_access,
)
from core.proxima_client import request

log = logging.getLogger("adm.admin_sync")


def _password_is_ours(row: dict) -> bool:
    """Has ADM set this password more recently than the site was told?

    An admin may change their password on the instance itself. Pushing on
    every sync would undo that silently, so the hash travels only when ADM's
    copy is the newer one.
    """
    changed = row.get("password_changed_at")
    synced = row.get("password_synced_at")
    if changed is None:
        return synced is None
    return synced is None or changed > synced


def _push_upsert(server: dict, row: dict) -> tuple[bool, str | None, bool]:
    """Create or update the account. Returns (ok, error, password_pushed)."""
    payload: dict = {"enabled": bool(row.get("admin_enabled", 1))}
    send_password = _password_is_ours(row)
    if send_password:
        payload["password_hash"] = row["password_hash"]

    try:
        r = request(server, "PUT", f"/api/admins/{row['username']}", body=payload)
    except Exception as e:  # noqa: BLE001 — surfaced to the operator verbatim
        return False, str(e), False

    if r.status_code in (200, 201):
        return True, None, send_password

    # An instance that has never seen this account rejects an update with no
    # hash. Retrying with one is the honest repair: the row is a grant, and
    # withholding the password would leave an account nobody can sign into.
    if r.status_code == 400 and not send_password:
        payload["password_hash"] = row["password_hash"]
        try:
            r = request(server, "PUT", f"/api/admins/{row['username']}", body=payload)
        except Exception as e:  # noqa: BLE001
            return False, str(e), False
        if r.status_code in (200, 201):
            return True, None, True

    return False, _error_of(r), False


def _push_delete(server: dict, row: dict) -> tuple[bool, str | None]:
    try:
        r = request(server, "DELETE", f"/api/admins/{row['username']}")
    except Exception as e:  # noqa: BLE001
        return False, str(e)

    # Already gone is the outcome we wanted.
    if r.status_code in (200, 404):
        return True, None
    return False, _error_of(r)


def _error_of(r) -> str:
    try:
        return (r.json() or {}).get("error") or f"HTTP {r.status_code}"
    except ValueError:
        return f"HTTP {r.status_code}"


def sync_pending(vpn_server_id: int | None = None,
                 admin_id: int | None = None,
                 allowed_server_ids: list[int] | None = None) -> dict:
    """Reconcile pending grants and revocations.

    allowed_server_ids confines the push to what the caller may write, so
    editing one operator cannot flush another site's queued changes.
    """
    rows = get_pending_admin_access(vpn_server_id)
    if admin_id is not None:
        rows = [r for r in rows if r["admin_id"] == admin_id]
    if allowed_server_ids is not None:
        rows = [r for r in rows if r["vpn_server_id"] in allowed_server_ids]

    servers = {s["id"]: s for s in get_all_vpn_servers()}
    granted: list[str] = []
    removed: list[str] = []
    failed: list[dict] = []

    for row in rows:
        server = servers.get(row["vpn_server_id"])
        label = f"{row['username']}@{row['server_name']}"

        if not server:
            mark_admin_access_error(row["id"], "VPN server missing")
            failed.append({"target": label, "error": "VPN server missing"})
            continue

        if row["sync_status"] == "pending_delete":
            ok, error = _push_delete(server, row)
            if ok:
                # Only now: until the site confirms, the instruction has to
                # survive so a failed revocation is retried rather than lost.
                delete_admin_access(row["admin_id"], row["vpn_server_id"])
                removed.append(label)
        else:
            ok, error, password_pushed = _push_upsert(server, row)
            if ok:
                mark_admin_access_synced(row["id"], password_pushed=password_pushed)
                granted.append(label)

        if not ok:
            mark_admin_access_error(row["id"], error or "Unknown error")
            failed.append({"target": label, "error": error})
            log.warning(f"[ADMIN-SYNC] Failed {label}: {error}")

    log.info(f"[ADMIN-SYNC] granted={len(granted)} removed={len(removed)} "
             f"failed={len(failed)}")
    return {"granted": granted, "removed": removed, "failed": failed}
