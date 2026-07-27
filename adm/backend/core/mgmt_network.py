"""The management network: ADM's own WireGuard interface for site call-home.

Sites dial out to here so they stay reachable whatever their router is or is
not forwarding. That path is the one that has to survive when everything else
is broken, which is why it is no longer a guest in wg-easy's configuration.

ADM used to register call-home peers by editing wg-easy's `wg0.json`. wg-easy
rewrites that file wholesale from its own state, so anything done in its UI
silently deleted ADM's peers — and on 2026-07-27 it did exactly that, removing
a live server's emergency access during unrelated work, with nothing reporting
it. Two writers, one file, no arbitration.

So the split is by population rather than by tool. wg-easy keeps `wg0` and the
humans on it: laptops and phones, added by hand, QR codes, all the things it
is good at. This interface carries only sites, and ADM is its only writer —
nobody clicks here, entries appear when a server is provisioned and go when it
is removed.
"""

import ipaddress
import logging
import os
import subprocess

from core.auth import decrypt_value, encrypt_value
from core.config import DB_PATH
from core.db import get_all_vpn_servers, get_vpn_server, update_vpn_server

log = logging.getLogger("adm.mgmt_network")

INTERFACE = os.environ.get("ADM_MGMT_INTERFACE", "wg-adm")
SUBNET = os.environ.get("ADM_MGMT_SUBNET", "10.12.12.0/24")
LISTEN_PORT = int(os.environ.get("ADM_MGMT_PORT", "51822"))
ENDPOINT = os.environ.get("ADM_MGMT_ENDPOINT", "vpn.ergunay.com")
CONF_PATH = os.environ.get("ADM_MGMT_CONF", f"/etc/wireguard/{INTERFACE}.conf")
# Kept beside the database rather than in /etc: this is ADM's state, and it
# should travel with the rest of it.
SERVER_KEY_PATH = os.environ.get(
    "ADM_MGMT_KEY", os.path.join(os.path.dirname(DB_PATH), "mgmt-server.key"))

# .1 is the interface itself; sites start after it.
FIRST_HOST = 10


def _wg(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["wg", *args], capture_output=True, text=True,
                          input=stdin, check=True).stdout.strip()


# ── Server identity ──────────────────────────────────────────────────────

def server_private_key() -> str:
    """This interface's key, created once and kept.

    Regenerating it would invalidate every site's configuration at once, so it
    is written with no group or world access and never rewritten.
    """
    if os.path.exists(SERVER_KEY_PATH):
        with open(SERVER_KEY_PATH) as f:
            key = f.read().strip()
        if key:
            return key

    key = _wg("genkey")
    fd = os.open(SERVER_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    log.info("[MGMT] Generated the management interface key")
    return key


def server_public_key() -> str:
    return _wg("pubkey", stdin=server_private_key())


# ── Addressing ───────────────────────────────────────────────────────────

def next_address() -> str | None:
    """The lowest free address in the management subnet."""
    network = ipaddress.ip_network(SUBNET, strict=True)
    taken = {s["callhome_ip"] for s in get_all_vpn_servers() if s.get("callhome_ip")}
    for host in network.hosts():
        if int(str(host).split(".")[-1]) < FIRST_HOST:
            continue
        if str(host) not in taken:
            return str(host)
    return None


# ── Interface configuration ──────────────────────────────────────────────

def render_conf() -> str:
    """Build the interface file from the servers ADM knows about.

    Generated whole, every time, from the database. There is no other writer,
    so there is nothing to merge with and nothing to preserve — which is the
    property that was missing before.
    """
    address = str(ipaddress.ip_network(SUBNET, strict=True).network_address + 1)
    prefix = SUBNET.split("/")[1]

    lines = [
        "# Managed by ADM — regenerated from the database, do not edit.",
        "# Sites dial in here; human devices belong on wg-easy's interface.",
        "[Interface]",
        f"Address    = {address}/{prefix}",
        f"ListenPort = {LISTEN_PORT}",
        f"PrivateKey = {server_private_key()}",
        "",
        # Sites have to reach each other's ADM-side services through here, and
        # an admin on wg-easy's interface has to reach the sites, so this
        # interface forwards rather than terminating.
        "PostUp   = sysctl -q -w net.ipv4.ip_forward=1",
        # Inserted at the head, not appended. ufw jumps to its own chains
        # early in FORWARD and the policy is DROP, so a rule at the end only
        # works if ufw happens not to have decided first. Depending on that
        # is how forwarding breaks silently months later.
        f"PostUp   = iptables -I FORWARD 1 -i {INTERFACE} -j ACCEPT",
        f"PostUp   = iptables -I FORWARD 1 -o {INTERFACE} -j ACCEPT",
        f"PostDown = iptables -D FORWARD -i {INTERFACE} -j ACCEPT",
        f"PostDown = iptables -D FORWARD -o {INTERFACE} -j ACCEPT",
    ]

    for server in get_all_vpn_servers():
        if not (server.get("callhome_pubkey") and server.get("callhome_ip")):
            continue
        lines += ["", f"# {server['name']}", "[Peer]",
                  f"PublicKey  = {server['callhome_pubkey']}"]
        psk = decrypt_value(server["callhome_psk_enc"]) if server.get("callhome_psk_enc") else None
        if psk:
            lines.append(f"PresharedKey = {psk}")
        lines.append(f"AllowedIPs = {server['callhome_ip']}/32")

    return "\n".join(lines) + "\n"


def write_conf() -> None:
    tmp = CONF_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(render_conf())
    os.replace(tmp, CONF_PATH)


def apply_live() -> None:
    """Load the current configuration without dropping established tunnels.

    `wg syncconf` reconciles peers in place; `wg-quick down/up` would tear the
    interface down and take every site with it, including whichever one is
    being worked on.
    """
    stripped = subprocess.run(["wg-quick", "strip", INTERFACE],
                              capture_output=True, text=True, check=True).stdout
    subprocess.run(["wg", "syncconf", INTERFACE, "/dev/stdin"],
                   input=stripped, text=True, check=True)


def is_up() -> bool:
    return subprocess.run(["wg", "show", INTERFACE], capture_output=True).returncode == 0


def sync() -> None:
    """Write the configuration and apply it if the interface is running."""
    write_conf()
    if is_up():
        apply_live()
        log.info("[MGMT] Interface reconciled")
    else:
        log.warning(f"[MGMT] {INTERFACE} is not up — configuration written only")


# ── Peers ────────────────────────────────────────────────────────────────

def ensure_peer(vpn_server_id: int) -> tuple[str | None, str | None]:
    """Give a site its place on the management network. Returns (config, error).

    Idempotent, and it keeps existing keys: re-provisioning a server must not
    change its tunnel identity, or the box would be cut off at the moment it
    is being repaired.
    """
    server = get_vpn_server(vpn_server_id)
    if not server:
        return None, "VPN server not found"

    updates: dict = {}
    address = server.get("callhome_ip")
    if not address:
        address = next_address()
        if not address:
            return None, "No free address left in the management network"
        updates["callhome_ip"] = address

    private_key = (decrypt_value(server["callhome_privkey_enc"])
                   if server.get("callhome_privkey_enc") else None)
    if not private_key:
        private_key = _wg("genkey")
        updates["callhome_privkey_enc"] = encrypt_value(private_key)
        updates["callhome_pubkey"] = _wg("pubkey", stdin=private_key)
        updates["callhome_psk_enc"] = encrypt_value(_wg("genpsk"))

    if updates:
        update_vpn_server(vpn_server_id, updates)
        server = get_vpn_server(vpn_server_id)
        log.info(f"[MGMT] Registered {server['name']} at {server['callhome_ip']}")

    sync()

    psk = decrypt_value(server["callhome_psk_enc"]) if server.get("callhome_psk_enc") else ""
    config = (
        "[Interface]\n"
        f"PrivateKey = {decrypt_value(server['callhome_privkey_enc'])}\n"
        f"Address    = {server['callhome_ip']}/{SUBNET.split('/')[1]}\n"
        "\n"
        "[Peer]\n"
        f"PublicKey    = {server_public_key()}\n"
        + (f"PresharedKey = {psk}\n" if psk else "")
        # The management network only. A site has its own LAN, and routing
        # ERG's into this tunnel would break it wherever the two overlap.
        + f"AllowedIPs   = {SUBNET}\n"
        f"Endpoint     = {ENDPOINT}:{LISTEN_PORT}\n"
        "PersistentKeepalive = 25\n"
    )
    return config, None


def forget_peer(vpn_server_id: int) -> None:
    """Drop a site from the network — its address returns to the pool."""
    update_vpn_server(vpn_server_id, {
        "callhome_ip": None, "callhome_pubkey": None,
        "callhome_privkey_enc": None, "callhome_psk_enc": None,
    })
    sync()


# ── Status ───────────────────────────────────────────────────────────────

def handshakes() -> dict[str, int]:
    """Seconds since each peer was last heard from, keyed by public key."""
    try:
        out = _wg("show", INTERFACE, "latest-handshakes")
    except (subprocess.CalledProcessError, OSError):
        return {}

    import time
    now = int(time.time())
    result = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) > 0:
            result[parts[0]] = now - int(parts[1])
    return result


def status() -> dict:
    """What the management network looks like right now."""
    seen = handshakes()
    peers = []
    for server in get_all_vpn_servers():
        if not server.get("callhome_pubkey"):
            continue
        peers.append({
            "vpn_server_id": server["id"],
            "name": server["name"],
            "display_name": server.get("display_name") or server["name"],
            "address": server.get("callhome_ip"),
            "last_handshake_seconds": seen.get(server["callhome_pubkey"]),
        })
    return {
        "interface": INTERFACE,
        "subnet": SUBNET,
        "listen_port": LISTEN_PORT,
        "endpoint": f"{ENDPOINT}:{LISTEN_PORT}",
        "up": is_up(),
        "peers": peers,
    }
