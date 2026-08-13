"""HTTP transport to Proxima instances.

Shared by the VPN-server proxy, the central user import and the user sync.
Every call is authenticated with the per-server admin token stored encrypted
in `vpn_servers.api_token_enc`.
"""

import logging

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
