"""The subnet register: what each site uses, and refusing two that overlap.

ADM does not allocate these. The number is decided at the router step, before
the box ships — the MikroTik's DHCP, routes and firewall are already built on
it, so a second authority picking independently would only ever be overruled.
What ADM does is remember them all and refuse one that collides.

The reason it is worth doing at all is that a collision is silent. Two sites
with the same range work perfectly until the day they have to reach each
other, and by then nobody remembers which one was typed second.
"""

import ipaddress
import logging

from core.db import get_all_vpn_servers

log = logging.getLogger("adm.subnets")

# The management network every site dials into. Nothing may overlap it: a site
# that did would be unable to reach ADM, which is the one path that has to
# survive whatever else is broken.
MANAGEMENT_NETWORK = "10.13.13.0/24"


def parse(value: str) -> tuple[ipaddress.IPv4Network | None, str | None]:
    """Parse a CIDR range, rejecting a host address given in place of one."""
    value = (value or "").strip()
    if not value:
        return None, None  # absent is allowed; unknown is not a conflict

    try:
        # strict=True so 10.14.14.1/24 is refused rather than quietly widened
        # to 10.14.14.0/24 — the two mean different things to whoever typed it,
        # and guessing which they meant is how a register stops matching
        # reality.
        network = ipaddress.ip_network(value, strict=True)
    except ValueError as e:
        return None, f"Not a valid network: {e}"

    if not isinstance(network, ipaddress.IPv4Network):
        return None, "Only IPv4 ranges are supported here"
    return network, None


def existing_ranges(exclude_server_id: int | None = None) -> list[dict]:
    """Every range ADM knows about, ready to be checked against."""
    ranges: list[dict] = [
        {"network": MANAGEMENT_NETWORK, "owner": "management network", "kind": "management"},
    ]
    for server in get_all_vpn_servers():
        if exclude_server_id is not None and server["id"] == exclude_server_id:
            continue
        label = server.get("display_name") or server["name"]
        for column, kind in (("vpn_subnet", "ProximaVPN"), ("lan_subnet", "LAN")):
            if server.get(column):
                ranges.append({"network": server[column], "owner": label, "kind": kind})
    return ranges


def check(value: str, exclude_server_id: int | None = None,
          also: list[str] | None = None) -> str | None:
    """Return why this range cannot be used, or None if it can.

    `also` carries ranges being submitted in the same breath — a site's own VPN
    and LAN ranges are entered together, and a form that accepted two
    overlapping halves of itself would have checked everything except the
    obvious.
    """
    network, error = parse(value)
    if error:
        return error
    if network is None:
        return None

    for other in also or []:
        other_network, other_error = parse(other)
        if other_network is not None and not other_error and network.overlaps(other_network):
            return f"{network} overlaps {other_network}, entered for the same site"

    for entry in existing_ranges(exclude_server_id):
        known, _ = parse(entry["network"])
        if known is not None and network.overlaps(known):
            return (f"{network} overlaps {known}, already used by "
                    f"{entry['owner']} ({entry['kind']})")
    return None


def validate_for_server(vpn_subnet: str, lan_subnet: str,
                        exclude_server_id: int | None = None) -> str | None:
    """Check both of a site's ranges together. Returns the first problem."""
    error = check(vpn_subnet, exclude_server_id, also=[])
    if error:
        return f"ProximaVPN subnet: {error}"
    error = check(lan_subnet, exclude_server_id, also=[vpn_subnet])
    if error:
        return f"LAN subnet: {error}"
    return None
