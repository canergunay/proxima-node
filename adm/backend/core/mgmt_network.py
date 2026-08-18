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
import json
import logging
import os
import secrets
import subprocess
import time

from core.auth import decrypt_value, encrypt_value
from core.config import DB_PATH
from core.db import (get_all_servers, get_all_vpn_servers, get_server,
                     get_vpn_server, update_server, update_vpn_server)

log = logging.getLogger("adm.mgmt_network")

INTERFACE = os.environ.get("ADM_MGMT_INTERFACE", "wg-adm")
SUBNET = os.environ.get("ADM_MGMT_SUBNET", "10.12.12.0/24")
LISTEN_PORT = int(os.environ.get("ADM_MGMT_PORT", "51822"))
ENDPOINT = os.environ.get("ADM_MGMT_ENDPOINT", "vpn.ergunay.com")
# Where the humans are — wg-easy's interface. Sites have to route it back or
# an admin reaching one gets no reply: the site would receive the packet and
# have nowhere to send the answer. Carried explicitly rather than masqueraded,
# so a site's logs name the device that reached it instead of showing every
# admin as the gateway.
ADMIN_NETWORK = os.environ.get("ADM_ADMIN_NETWORK", "10.13.13.0/24")
# awg-quick reads /etc/amnezia/amneziawg, not /etc/wireguard, and will not
# find a file left in the latter.
CONF_PATH = os.environ.get(
    "ADM_MGMT_CONF", f"/etc/amnezia/amneziawg/{INTERFACE}.conf")
# Kept beside the database rather than in /etc: this is ADM's state, and it
# should travel with the rest of it.
SERVER_KEY_PATH = os.environ.get(
    "ADM_MGMT_KEY", os.path.join(os.path.dirname(DB_PATH), "mgmt-server.key"))

# AmneziaWG rather than plain WireGuard. Plain WG is a protocol Russian DPI
# recognises, and the services on these nodes have been disappearing one
# transport at a time — TCP first. The obfuscation parameters live beside the
# interface key because they are part of its identity: change them and every
# node's configuration stops matching at once.
AWG_PARAMS_PATH = os.environ.get(
    "ADM_MGMT_AWG_PARAMS",
    os.path.join(os.path.dirname(DB_PATH), "mgmt-awg-params.json"))
# The tools are AmneziaWG's forks of wg/wg-quick. They read the same key
# format, so nothing about existing peers changes when the transport does.
WG_BIN = os.environ.get("ADM_MGMT_WG_BIN", "awg")
WG_QUICK_BIN = os.environ.get("ADM_MGMT_WG_QUICK_BIN", "awg-quick")

# .1 is the interface itself; sites start after it.
FIRST_HOST = 10
# Exit nodes sit in their own decade, so an address says which population it
# belongs to and the two allocators cannot hand out the same one.
FIRST_EXIT_HOST = 100


def _wg(*args: str, stdin: str | None = None) -> str:
    return subprocess.run([WG_BIN, *args], capture_output=True, text=True,
                          input=stdin, check=True).stdout.strip()


# ── Obfuscation ──────────────────────────────────────────────────────────

def awg_params() -> dict:
    """The interface's AmneziaWG parameters, created once and kept.

    Both ends must agree exactly, so these are generated on first use and
    then never rewritten — regenerating them would silently invalidate every
    node's configuration, the same reason the interface key is written once.

    The constraints are AmneziaWG's own: the four header markers have to be
    distinct and above the four message types they stand in for, and the two
    junk sizes must not collide once the response header is added, or an
    initiation and a response become indistinguishable.
    """
    if os.path.exists(AWG_PARAMS_PATH):
        with open(AWG_PARAMS_PATH) as f:
            params = json.load(f)
        if params:
            return params

    headers = set()
    while len(headers) < 4:
        headers.add(secrets.randbelow(0x7FFFFFFF - 5) + 5)
    h1, h2, h3, h4 = sorted(headers)

    s1 = secrets.randbelow(100) + 15
    s2 = secrets.randbelow(100) + 15
    while s2 == s1 + 56:
        s2 = secrets.randbelow(100) + 15

    params = {
        "Jc": secrets.randbelow(5) + 3,      # junk packets before the handshake
        "Jmin": 40,
        "Jmax": 70,
        "S1": s1,                            # junk prepended to the initiation
        "S2": s2,                            # junk prepended to the response
        "H1": h1, "H2": h2, "H3": h3, "H4": h4,
    }

    fd = os.open(AWG_PARAMS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(params, f, indent=2)
    log.info("[MGMT] Generated the interface's obfuscation parameters")
    return params


def _awg_lines() -> list[str]:
    """The parameters as configuration lines, in AmneziaWG's declared order."""
    p = awg_params()
    return [f"{k} = {p[k]}" for k in
            ("Jc", "Jmin", "Jmax", "S1", "S2", "H1", "H2", "H3", "H4")]


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

def _enrolled() -> list[dict]:
    """Every row on the network, from both populations, tagged with its kind.

    Sites and exit nodes live in different tables with the same four columns.
    The interface does not care which is which, but the address allocator has
    to: one subnet serves both.
    """
    return ([{**site, "kind": "vpn"} for site in get_all_vpn_servers()]
            + [{**node, "kind": "exit"} for node in get_all_servers()])


def next_address(exit_node: bool = False) -> str | None:
    """The lowest free address in the management subnet.

    Addresses taken by *either* population are excluded. Nothing else would
    stop a site and an exit node being handed the same one on different days.
    """
    network = ipaddress.ip_network(SUBNET, strict=True)
    taken = {r["callhome_ip"] for r in _enrolled() if r.get("callhome_ip")}
    floor = FIRST_EXIT_HOST if exit_node else FIRST_HOST
    for host in network.hosts():
        if int(str(host).split(".")[-1]) < floor:
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
        *_awg_lines(),
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

    for server in _enrolled():
        if not (server.get("callhome_pubkey") and server.get("callhome_ip")):
            continue
        lines += ["", f"# {server['name']} ({server['kind']})", "[Peer]",
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
    stripped = subprocess.run([WG_QUICK_BIN, "strip", INTERFACE],
                              capture_output=True, text=True, check=True).stdout
    subprocess.run([WG_BIN, "syncconf", INTERFACE, "/dev/stdin"],
                   input=stripped, text=True, check=True)


def is_up() -> bool:
    return subprocess.run([WG_BIN, "show", INTERFACE], capture_output=True).returncode == 0


# How long a peer may go without a handshake before we call the tunnel dead.
# WireGuard rekeys about every two minutes while anything is flowing, and every
# config here sets PersistentKeepalive=25, so a live peer is never quiet for
# five minutes. Anything older means the tunnel is down, whatever the node's
# agent says over its public address.
STALE_AFTER = 300


def peer_status() -> dict[str, dict]:
    """Last-handshake state per peer, keyed by public key.

    Read straight from the interface rather than inferred from agent polling.
    That distinction is the whole point: `_proxy_request` falls back to a
    node's public address when the tunnel does not answer, so a node reports
    itself healthy while the recovery path it is supposed to be reachable
    through has been dead for days. Nothing surfaced that until it was looked
    for by hand — two of six tunnels turned out to be down, one for six and a
    half days.

    Returns {} when the interface is not up, which callers must treat as
    "unknown", not "everything is down".
    """
    try:
        dump = _wg("show", INTERFACE, "dump")
    except Exception:
        return {}

    now = time.time()
    peers: dict[str, dict] = {}
    # First line describes the interface itself; peers follow, tab separated:
    # pubkey, psk, endpoint, allowed-ips, last-handshake, rx, tx, keepalive
    for line in dump.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        pubkey, _psk, endpoint, allowed, handshake, rx, tx = parts[:7]
        try:
            last = int(handshake)
        except ValueError:
            last = 0
        age = int(now - last) if last else None
        peers[pubkey] = {
            "endpoint": None if endpoint == "(none)" else endpoint,
            "allowed_ips": allowed,
            "handshake_age": age,
            "rx_bytes": int(rx) if rx.isdigit() else 0,
            "tx_bytes": int(tx) if tx.isdigit() else 0,
            # never  — configured but has not once completed a handshake
            # up     — seen within STALE_AFTER
            # stale  — was up at some point, is not now
            "state": "never" if age is None else ("up" if age <= STALE_AFTER else "stale"),
        }
    return peers


def tunnel_for(server: dict, peers: dict[str, dict] | None) -> dict:
    """The management-tunnel view of one server, for the API to embed.

    `peers` is passed in so a list endpoint reads the interface once instead of
    once per row.
    """
    pubkey = server.get("callhome_pubkey")
    if not pubkey:
        return {"state": "absent"}
    if peers is None:
        return {"state": "unknown"}
    return peers.get(pubkey, {"state": "absent"})


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
        + "".join(f"{line}\n" for line in _awg_lines())
        + "\n"
        "[Peer]\n"
        f"PublicKey    = {server_public_key()}\n"
        + (f"PresharedKey = {psk}\n" if psk else "")
        # The management network and the admins' own — nothing more. A site
        # has its own LAN, and routing ERG's into this tunnel would break it
        # wherever the two overlap.
        + f"AllowedIPs   = {SUBNET}, {ADMIN_NETWORK}\n"
        f"Endpoint     = {ENDPOINT}:{LISTEN_PORT}\n"
        "PersistentKeepalive = 25\n"
    )
    return config, None


def ensure_exit_peer(server_id: int) -> tuple[str | None, str | None]:
    """Give an exit node its place on the management network.

    Same contract as ensure_peer, against the other table. Exit nodes have no
    inbound requirement at all once this is up: the agent port can be closed
    to the internet, which removes both the failure where a stalled scanner on
    5051 freezes the agent and the one where a blocked route to the public
    address makes a healthy node report as offline.
    """
    server = get_server(server_id)
    if not server:
        return None, "Exit server not found"

    updates: dict = {}
    address = server.get("callhome_ip")
    if not address:
        address = next_address(exit_node=True)
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
        update_server(server_id, updates)
        server = get_server(server_id)
        log.info(f"[MGMT] Registered exit node {server['name']} "
                 f"at {server['callhome_ip']}")

    sync()

    psk = decrypt_value(server["callhome_psk_enc"]) if server.get("callhome_psk_enc") else ""
    config = (
        "# Managed by ADM. AmneziaWG, not plain WireGuard: install as\n"
        "# /etc/amnezia/amneziawg/wg-adm.conf and bring up with awg-quick.\n"
        "[Interface]\n"
        f"PrivateKey = {decrypt_value(server['callhome_privkey_enc'])}\n"
        f"Address    = {server['callhome_ip']}/{SUBNET.split('/')[1]}\n"
        + "".join(f"{line}\n" for line in _awg_lines())
        + "\n"
        "[Peer]\n"
        f"PublicKey    = {server_public_key()}\n"
        + (f"PresharedKey = {psk}\n" if psk else "")
        # Carrying the admin range is what lets a human reach a node whose
        # public address has stopped answering — the case this path exists for.
        + f"AllowedIPs   = {SUBNET}, {ADMIN_NETWORK}\n"
        f"Endpoint     = {ENDPOINT}:{LISTEN_PORT}\n"
        # The node dials out and keeps the tunnel warm. Nothing dials in, so
        # there is no port forward to maintain and CGNAT is not a problem.
        "PersistentKeepalive = 25\n"
    )
    return config, None


def forget_exit_peer(server_id: int) -> None:
    """Drop an exit node from the network — its address returns to the pool."""
    update_server(server_id, {
        "callhome_ip": None, "callhome_pubkey": None,
        "callhome_privkey_enc": None, "callhome_psk_enc": None,
    })
    sync()


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
    for server in _enrolled():
        if not server.get("callhome_pubkey"):
            continue
        peers.append({
            "kind": server["kind"],
            "vpn_server_id": server["id"] if server["kind"] == "vpn" else None,
            "server_id": server["id"] if server["kind"] == "exit" else None,
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
