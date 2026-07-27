"""Install Proxima on a site server and claim it.

The order is deliberate. The call-home tunnel is established first, so the
box is reachable from ERG before anything else happens — a failed or
half-finished install cannot strand it, whatever the site's router is or is
not forwarding. Only then is Proxima installed, and only then does ADM claim
the instance and store a token for it.

Once claimed, the SSH password is discarded: ADM has its key on the box and
an API token, so keeping a site's password would be a liability with nothing
left to justify it.
"""

import base64
import logging
import os
import subprocess

import requests

from core.auth import encrypt_value
from core.db import (
    create_operation,
    get_vpn_server,
    update_vpn_server,
)
from core.inventory_writer import regenerate_for_vpn_server

log = logging.getLogger("adm.vpn_provision")

PROXIMA_SRC = os.environ.get("ADM_PROXIMA_SRC", "/opt/erg/proxima-src")
PROXIMA_PORT = 5050


# ── Claiming ─────────────────────────────────────────────────────────────

def claim_instance(url: str, username: str,
                   password_hash: str) -> tuple[str | None, str | None]:
    """Create the first admin on a fresh instance and keep its token.

    The operator's existing hash is what gets planted, so setting up a server
    invents no new credential: they sign into the new panel with the password
    they already use for ADM. Werkzeug's pbkdf2 format is shared by both
    sides, and ADM never holds the plaintext to send.

    Returns (token, error). An instance that already has an admin cannot be
    claimed this way — that is reported rather than worked around, because it
    means the box was not as fresh as the operator believed.
    """
    try:
        r = requests.post(f"{url}/api/auth/setup",
                          json={"username": username, "password_hash": password_hash},
                          timeout=20, verify=True)
    except requests.RequestException as e:
        return None, f"Cannot reach the new instance: {e}"

    try:
        payload = r.json()
    except ValueError:
        return None, f"HTTP {r.status_code}: non-JSON response"

    if r.status_code == 409:
        return None, ("This instance already has an admin account — it was not "
                      "a fresh install. Register it manually with its token.")
    if not payload.get("ok"):
        return None, payload.get("error") or f"HTTP {r.status_code}"

    token = (payload.get("data") or {}).get("token")
    if not token:
        return None, "Setup succeeded but returned no token"
    return token, None


# ── Provisioning ─────────────────────────────────────────────────────────

def start_provision(vpn_server_id: int, admin_id: int | None = None,
                    claim: bool = True) -> tuple[int | None, str | None]:
    """Kick off the install. Returns (operation_id, error).

    Runs in the background; the operation log carries the playbook output and
    the claim result, so the caller can follow it in the UI.

    admin_id is the operator running this. They become the new instance's
    first panel admin, using the password they already have — no credential
    is generated, and none has to be written down or handed over.

    claim=False re-deploys a server ADM already owns: the same playbook syncs
    the newer source and re-runs the installer, but there is no first admin to
    create and no token to fetch.
    """
    from core.ansible_runner import is_running, run_playbook

    server = get_vpn_server(vpn_server_id)
    if not server:
        return None, "VPN server not found"
    if not server.get("ssh_host"):
        return None, "No SSH host recorded for this server"
    if is_running():
        return None, "Another Ansible operation is already running"

    # The management network is ADM's own interface, not a guest in wg-easy's
    # configuration — see core.mgmt_network for why that had to change.
    from core.mgmt_network import ensure_peer
    try:
        conf, error = ensure_peer(vpn_server_id)
    except (OSError, subprocess.CalledProcessError) as e:
        log.exception("[PROVISION] Call-home peer setup failed")
        return None, f"Could not register the call-home peer: {e}"
    if error:
        return None, error

    server = get_vpn_server(vpn_server_id)
    address = server["callhome_ip"]
    regenerate_for_vpn_server(server)

    op_id = create_operation(None, "provision_proxima", "setup-proxima.yml")

    def on_complete(success: bool, _op_id: int) -> None:
        if not success:
            log.warning(f"[PROVISION] Playbook failed for {server['name']}")
            return
        if not claim:
            log.info(f"[PROVISION] Re-deployed {server['name']}")
            return
        _finish_provision(vpn_server_id, address, admin_id, _op_id)

    run_playbook(
        op_id, "setup-proxima.yml",
        limit=server["name"],
        extra_vars={
            "server_code": server.get("server_code") or server["name"].upper()[:5],
            "callhome_conf_b64": base64.b64encode(conf.encode()).decode(),
            "proxima_src": PROXIMA_SRC,
        },
        on_complete=on_complete,
    )
    return op_id, None


def _finish_provision(vpn_server_id: int, address: str, admin_id: int | None,
                      op_id: int) -> None:
    """Claim the freshly installed instance and drop the SSH password."""
    from core.db import append_operation_output, get_admin, grant_admin_access

    admin = get_admin(admin_id) if admin_id else None
    if not admin:
        append_operation_output(
            op_id, "\n[ADM] Cannot claim: the operator who started this is gone.\n")
        log.error(f"[PROVISION] No admin {admin_id} to claim server {vpn_server_id}")
        return

    # Reached over the management tunnel, not the site's LAN address: this is
    # the path that keeps working once the box is at a remote site.
    url = f"http://{address}:{PROXIMA_PORT}"
    token, error = claim_instance(url, admin["username"], admin["password_hash"])

    if error:
        append_operation_output(op_id, f"\n[ADM] Could not claim the instance: {error}\n")
        log.error(f"[PROVISION] Claim failed for server {vpn_server_id}: {error}")
        return

    update_vpn_server(vpn_server_id, {
        "url": url,
        "api_token_enc": encrypt_value(token),
        # The password existed to get in the first time. ADM's key is on the
        # box now and it has a token; holding the site's password any longer
        # is exposure without purpose.
        "ssh_password_enc": None,
    })
    regenerate_for_vpn_server(get_vpn_server(vpn_server_id))

    # Record what the claim just created, so the panel-access matrix shows
    # this operator on the new site instead of an account ADM does not know
    # about. Already synced by definition — setup planted it.
    grant_admin_access(admin_id, vpn_server_id)
    from core.db import get_admin_access, mark_admin_access_synced
    for row in get_admin_access(admin_id):
        if row["vpn_server_id"] == vpn_server_id:
            mark_admin_access_synced(row["id"], password_pushed=True)
            break

    append_operation_output(
        op_id,
        f"\n[ADM] Instance claimed at {url} as '{admin['username']}' — sign in "
        f"with your usual password. API token stored and the SSH password "
        f"discarded.\n")
    log.info(f"[PROVISION] Claimed server {vpn_server_id} at {url} "
             f"as '{admin['username']}'")


# ── Version drift ────────────────────────────────────────────────────────

def source_revision() -> dict | None:
    """The revision ADM would deploy right now."""
    try:
        out = subprocess.run(
            ["git", "-C", PROXIMA_SRC, "log", "-1", "--format=%H%n%ct"],
            capture_output=True, text=True, check=True).stdout.split()
        return {"commit": out[0], "short": out[0][:7], "committed_at": int(out[1])}
    except (subprocess.CalledProcessError, OSError, IndexError, ValueError):
        return None


def update_source() -> tuple[dict | None, str | None]:
    """Fetch the latest source so a later deploy carries it."""
    try:
        subprocess.run(["git", "-C", PROXIMA_SRC, "fetch", "--quiet", "origin"],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", PROXIMA_SRC, "reset", "--quiet",
                        "--hard", "origin/main"],
                       check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, OSError) as e:
        detail = getattr(e, "stderr", "") or str(e)
        return None, f"Could not update the source checkout: {detail.strip()}"
    return source_revision(), None
