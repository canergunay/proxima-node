"""HTTP transport to Proxima instances.

Shared by the VPN-server proxy, the central user import and the user sync.
Every call is authenticated with the per-server admin token stored encrypted
in `vpn_servers.api_token_enc`.
"""

import base64
import json
import logging
import time

import requests

from core.auth import decrypt_value

log = logging.getLogger("adm.proxima_client")

DEFAULT_TIMEOUT = 15

# For probes a human is waiting on, split the budget: a short connect timeout
# and a longer read one. A powered-off site does not refuse the connection, it
# simply never answers, so a single scalar timeout is spent in full on the
# connect — and because the dashboard cannot render until every instance has
# answered, its load time became the worst site's timeout. Two seconds is two
# orders of magnitude above the real RTT to any of our sites (Moscow-to-Moscow
# is ~5 ms, the interconnect ~6 ms), so this cannot cost a reachable server its
# place in the list. The read half stays generous: an instance that is slow to
# answer is still worth waiting for.
PROBE_TIMEOUT: tuple[int, int] = (2, 8)

# TLS is verified. Every Proxima instance is reached either over loopback
# (plain http, where this is a no-op) or over a public HTTPS endpoint with a
# real certificate. A site with a self-signed certificate would fail loudly
# here — which is the intent; carrying admin tokens and password hashes over
# an unverified channel is not an acceptable default.
VERIFY_TLS = True


# Proxima admin tokens are JWTs that expire (TOKEN_EXPIRY_DAYS on the site,
# 90 days). ADM stores one per site and replays it; until 2026-09-20 nothing
# renewed them, so ERG's and SHV's died on 2026-09-18 and every user sync
# failed with 401 — visible only in the journal. The scheduler now refreshes a
# token this far ahead of its expiry, and the UI names an expired one.
TOKEN_REFRESH_AHEAD = 30 * 86400


def token_expiry(server: dict) -> int | None:
    """Unix expiry of the stored site token, read from the JWT payload.

    Not verified — ADM does not hold the site's secret and does not need to:
    this decides *when to refresh*, and the site still judges validity.
    """
    enc_token = server.get("api_token_enc")
    if not enc_token:
        return None
    token = decrypt_value(enc_token)
    if not token:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return int(exp) if exp else None
    except Exception:  # noqa: BLE001 — an unreadable token is simply "unknown"
        return None


def token_state(server: dict) -> str:
    """'none', 'expired', 'expiring' (within TOKEN_REFRESH_AHEAD) or 'ok'."""
    if not server.get("api_token_enc"):
        return "none"
    exp = token_expiry(server)
    if exp is None:
        return "ok"  # a token we cannot read is left to the site to judge
    now = time.time()
    if exp <= now:
        return "expired"
    if exp - now < TOKEN_REFRESH_AHEAD:
        return "expiring"
    return "ok"


def refresh_token(server: dict) -> tuple[str | None, str | None]:
    """Trade the stored (still valid) token for a fresh one. Returns (token, error)."""
    data, error = call(server, "POST", "/api/auth/refresh")
    if error:
        return None, error
    token = (data or {}).get("token") if isinstance(data, dict) else None
    if not token:
        return None, "No token in refresh response"
    return token, None


def auth_headers(server: dict) -> dict:
    """Bearer header for a Proxima instance, empty if no token is stored."""
    enc_token = server.get("api_token_enc")
    if not enc_token:
        return {}
    token = decrypt_value(enc_token)
    return {"Authorization": f"Bearer {token}"} if token else {}


def request(server: dict, method: str, path: str, body: dict | None = None,
            timeout: int | tuple[int, int] = DEFAULT_TIMEOUT) -> requests.Response:
    """Forward a request to a Proxima instance. Returns the raw response."""
    url = f"{server['url'].rstrip('/')}{path}"
    headers = auth_headers(server)

    if method == "GET":
        return requests.get(url, headers=headers, timeout=timeout, verify=VERIFY_TLS)
    if method == "POST":
        return requests.post(url, json=body, headers=headers, timeout=timeout, verify=VERIFY_TLS)
    if method == "PUT":
        return requests.put(url, json=body, headers=headers, timeout=timeout, verify=VERIFY_TLS)
    if method == "DELETE":
        return requests.delete(url, headers=headers, timeout=timeout, verify=VERIFY_TLS)
    raise ValueError(f"Unsupported method: {method}")


def call(server: dict, method: str, path: str, body: dict | None = None,
         timeout: int | tuple[int, int] = DEFAULT_TIMEOUT) -> tuple[object | None, str | None]:
    """Call a Proxima endpoint and unwrap its {ok, data} envelope.

    Returns (data, None) on success or (None, error_message) on any failure —
    transport, HTTP status or application-level error.
    """
    if not server.get("api_token_enc"):
        return None, "No API token configured"

    try:
        resp = request(server, method, path, body=body, timeout=timeout)
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach Proxima instance"
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except Exception as e:  # noqa: BLE001 — surfaced to the operator as text
        return None, str(e)

    try:
        payload = resp.json()
    except ValueError:
        return None, f"HTTP {resp.status_code}: non-JSON response"

    if not payload.get("ok"):
        return None, payload.get("error") or f"HTTP {resp.status_code}"

    return payload.get("data"), None
