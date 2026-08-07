"""Single-login discovery — the one endpoint the ProximaVPN client's
username+password login talks to (master plan Section 21).

ADM answers "where", the instances answer "who": this endpoint never
verifies the password itself. It forwards the credentials to one of the
user's own instances' existing /api/vpn/auth/login over the verified-TLS
admin channel and, if that instance accepts, returns the public addresses
of every server the user is granted. ADM's stored hash is deliberately not
in the login path — it can be arbitrarily stale (users change passwords
from the client) and discovery still works, because the instance the user
actually uses is the thing consulted.

Unauthenticated by design (it IS the login), so it carries its own rate
limiting: a per-identity "ip|username" tier plus a coarse per-address
backstop. Counting by address alone would let one person's typo lock out
every colleague behind the same NAT.
"""

import logging
import random
import time

import requests
from flask import Blueprint, jsonify, request

from core.auth import (
    MAX_ATTEMPTS_PER_IP,
    check_rate_limit,
    clear_login_failures,
    record_login_failure,
)
from core.db import (
    get_all_vpn_servers,
    get_user_access,
    get_vpn_servers_last_online,
    get_vpn_user_by_username,
)
from core.proxima_client import request as proxima_request

log = logging.getLogger("adm.vpn_discover")
bp = Blueprint("vpn_discover", __name__)

# The forwarded login must fail fast: a down site should cost one timeout,
# not hold the client's login spinner for the transport default.
DELEGATE_TIMEOUT = 10

GENERIC_401 = {"ok": False, "error": "Invalid credentials"}


def _dummy_delay() -> None:
    """Approximate a delegation round-trip on paths that never delegate.

    Unknown users and userless grants return without touching any instance;
    without this, "known username" would fall straight out of response time.
    """
    time.sleep(random.uniform(0.1, 0.3))


def _delegation_order(access: list[dict]) -> list[dict]:
    """Enabled grants, last-known-online sites first, then by server id."""
    online = get_vpn_servers_last_online()
    rows = [a for a in access if a["enabled"]]
    # False sorts before True, so negate: online → 0, offline/unknown → 1.
    rows.sort(key=lambda a: (0 if online.get(a["vpn_server_id"]) else 1,
                             a["vpn_server_id"]))
    return rows


def _delegate(server: dict, username: str, password: str) -> str:
    """Ask one instance whether these credentials are valid.

    Returns "ok", "rejected", "throttled", or "unreachable". A 401/403 from
    a reachable instance is authoritative — the caller must stop, not try
    the next site, or one discover call becomes a password spray across
    every site the user has.
    """
    try:
        resp = proxima_request(
            server, "POST", "/api/vpn/auth/login",
            body={"username": username, "password": password},
            timeout=DELEGATE_TIMEOUT,
        )
    except requests.RequestException:
        return "unreachable"

    if resp.status_code in (401, 403):
        return "rejected"
    if resp.status_code == 429:
        return "throttled"
    if resp.status_code != 200:
        # A malfunctioning site (5xx, proxy error page) verifies nothing
        # either way — treat like a site that is down.
        return "unreachable"

    try:
        ok = bool(resp.json().get("ok"))
    except ValueError:
        return "unreachable"
    return "ok" if ok else "rejected"


@bp.post("/api/vpn/discover")
def discover():
    """Authenticate a VPN app user and return their servers' public URLs."""
    ip = request.remote_addr or "unknown"

    # Coarse per-address backstop, before the body is even parsed.
    lockout = check_rate_limit(ip, MAX_ATTEMPTS_PER_IP)
    if lockout:
        log.warning(f"[DISCOVER] Rate limited (address): {ip} ({lockout}s remaining)")
        return jsonify({"ok": False, "error": "Too many attempts. Try again later.",
                        "retry_after": lockout}), 429

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400

    ident = f"{ip}|{username.lower()}"
    lockout = check_rate_limit(ident)
    if lockout:
        log.warning(f"[DISCOVER] Rate limited: '{username}' from {ip} "
                    f"({lockout}s remaining)")
        return jsonify({"ok": False, "error": "Too many attempts. Try again later.",
                        "retry_after": lockout}), 429

    user = get_vpn_user_by_username(username)
    if not user or not user["enabled"]:
        record_login_failure(ident, ip)
        log.warning(f"[DISCOVER] Rejected '{username}' from {ip} "
                    f"({'disabled' if user else 'unknown user'})")
        _dummy_delay()
        return jsonify(GENERIC_401), 401

    grants = _delegation_order(get_user_access(user["id"]))
    if not grants:
        # An account with no active site cannot be verified by anyone —
        # indistinguishable from a bad password on purpose.
        record_login_failure(ident, ip)
        log.warning(f"[DISCOVER] '{username}' from {ip} has no enabled grants")
        _dummy_delay()
        return jsonify(GENERIC_401), 401

    servers = {s["id"]: s for s in get_all_vpn_servers()}

    verdict = "unreachable"
    for grant in grants:
        server = servers.get(grant["vpn_server_id"])
        if not server:
            continue
        verdict = _delegate(server, username, password)
        if verdict != "unreachable":
            break

    if verdict == "rejected":
        record_login_failure(ident, ip)
        log.warning(f"[DISCOVER] Rejected '{username}' from {ip} "
                    f"(instance said no)")
        return jsonify(GENERIC_401), 401
    if verdict == "throttled":
        # The instance is counting ADM's failures for this identity; back
        # off rather than trying its siblings with the same password.
        log.warning(f"[DISCOVER] Instance throttled '{username}' (via {ip})")
        return jsonify({"ok": False, "error": "Too many attempts. Try again later.",
                        "retry_after": 300}), 429
    if verdict != "ok":
        log.warning(f"[DISCOVER] No instance reachable to verify '{username}' "
                    f"from {ip}")
        return jsonify({"ok": False,
                        "error": "No server reachable to verify login. "
                                 "Try again later."}), 503

    clear_login_failures(ident, ip)

    result = []
    for grant in grants:
        server = servers.get(grant["vpn_server_id"])
        if not server:
            continue
        public_url = (server.get("public_url") or "").rstrip("/")
        if not public_url:
            # url is the ADM→instance path (possibly a management network
            # address) and must never reach a user's device.
            log.warning(f"[DISCOVER] {server['name']} has no public_url — "
                        f"hidden from '{username}'")
            continue
        result.append({
            "display_name": server.get("display_name") or server["name"],
            "public_url": public_url,
            "server_code": server.get("server_code") or server["name"],
        })

    log.info(f"[DISCOVER] '{username}' from {ip}: {len(result)} server(s)")
    return jsonify({"ok": True, "data": {
        "user": {"username": user["username"]},
        "servers": result,
    }})
