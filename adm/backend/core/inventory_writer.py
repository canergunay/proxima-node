"""Generate Ansible inventory files from database.

Generates:
  - inventory/hosts.yml   (all servers, grouped by type)
  - inventory/host_vars/<name>.yml  (per-server credentials)

Does NOT touch inventory/group_vars/ — those stay committed in git.
"""

import logging
import os

import yaml

from core.auth import decrypt_value
from core.config import REPO_ROOT
from core.db import get_all_servers, get_all_vpn_servers

log = logging.getLogger("adm.inventory")

INVENTORY_DIR = os.path.join(REPO_ROOT, "inventory")
HOSTS_YML = os.path.join(INVENTORY_DIR, "hosts.yml")
HOST_VARS_DIR = os.path.join(INVENTORY_DIR, "host_vars")


def _atomic_write(path: str, content: str) -> None:
    """Write to a temp file then rename for crash safety."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)


def _live_tunnels() -> dict:
    """Peers that have handshaked recently, by public key.

    Reading `wg show` rather than trusting the database. A row having a
    callhome_ip only means an address was allocated — the tunnel may never
    have been installed, or may have stopped carrying traffic. Pointing
    Ansible at an address on that evidence is how a provision fails with
    "unreachable" against a box whose public address was fine all along.

    Failure here is deliberately quiet: an empty result sends everything to
    its public address, which is the safe direction to be wrong in.
    """
    try:
        from core.mgmt_network import handshakes
        return handshakes()
    except Exception:
        log.debug("Could not read management tunnel handshakes", exc_info=True)
        return {}


# Keepalive is 25s, so a tunnel carrying traffic handshakes well inside this.
TUNNEL_FRESH_SECONDS = 180


def _management_host(row: dict, public: str | None, live: dict | None = None) -> dict:
    """Which address Ansible should use, and the other one written beside it.

    The management tunnel when the node is on it. Ansible is management, and
    the tunnel is the path built to survive what has been taking the public
    addresses away — two of four exit nodes stopped answering publicly from
    Russia within a day of each other, and running a play against them meant
    passing -e ansible_host by hand every time.

    But only a tunnel that is actually up. An allocated address is not a
    working path: a node enrolled before it was provisioned has a callhome_ip
    and nothing listening on it, and choosing that would fail the provision
    against a box whose public address was reachable the whole time. So the
    decision comes from a recent handshake, not from the database — the same
    correction the role needed, made in the same wrong place twice.

    public_host is recorded either way, so the override for an unusual case
    is `-e ansible_host={{ public_host }}` rather than a hunt for the address.
    """
    entry: dict = {}
    tunnel = row.get("callhome_ip")
    pubkey = row.get("callhome_pubkey")
    seen = (live or {}).get(pubkey) if pubkey else None
    tunnel_up = tunnel and seen is not None and seen <= TUNNEL_FRESH_SECONDS

    entry["ansible_host"] = tunnel if tunnel_up else public
    if public:
        entry["public_host"] = public
    if tunnel:
        entry["mgmt_tunnel_host"] = tunnel
    return entry


def write_hosts_yml(servers: list[dict], vpn_servers: list[dict] | None = None) -> None:
    """Generate inventory/hosts.yml from the server lists.

    Exit nodes and site servers are different animals and land in different
    groups. Exit nodes are VPS images where root logs in with a password;
    site servers are machines installed from Debian netinst, where the
    default `PermitRootLogin prohibit-password` makes that impossible — so
    those carry their own user and escalate with sudo.
    """
    vpn_exit_hosts = {}
    dpi_bypass_hosts = {}
    proxima_site_hosts = {}
    live = _live_tunnels()

    for s in vpn_servers or []:
        if not s.get("ssh_host"):
            continue  # registered by hand, not provisioned by ADM
        entry = _management_host(s, s["ssh_host"], live)
        if s.get("ssh_port") and s["ssh_port"] != 22:
            entry["ansible_port"] = s["ssh_port"]
        entry["ansible_user"] = s.get("ssh_user") or "root"
        if entry["ansible_user"] != "root":
            entry["ansible_become"] = True
        if s.get("server_code"):
            entry["server_code"] = s["server_code"]
        proxima_site_hosts[s["name"]] = entry

    for s in servers:
        if s["status"] == "decommissioned":
            continue
        host_entry = _management_host(s, s["ip"], live)
        ssh_port = s.get("ssh_port", 22)
        if ssh_port and ssh_port != 22:
            host_entry["ansible_port"] = ssh_port
        if s.get("location"):
            host_entry["server_location"] = s["location"]
        if s.get("provider"):
            host_entry["server_provider"] = s["provider"]

        if s["server_type"] == "vpn_exit":
            vpn_exit_hosts[s["name"]] = host_entry
        elif s["server_type"] == "dpi_bypass":
            dpi_bypass_hosts[s["name"]] = host_entry

    inventory = {
        "all": {
            "children": {},
            "vars": {
                "ansible_user": "root",
                "ansible_python_interpreter": "/usr/bin/python3",
            },
        }
    }

    if vpn_exit_hosts:
        inventory["all"]["children"]["vpn_exit"] = {"hosts": vpn_exit_hosts}
    if dpi_bypass_hosts:
        inventory["all"]["children"]["dpi_bypass"] = {"hosts": dpi_bypass_hosts}
    if proxima_site_hosts:
        inventory["all"]["children"]["proxima_sites"] = {"hosts": proxima_site_hosts}

    content = yaml.dump(inventory, default_flow_style=False, sort_keys=False, allow_unicode=True)
    _atomic_write(HOSTS_YML, content)
    log.info(f"[INVENTORY] hosts.yml written ({len(vpn_exit_hosts)} vpn_exit, "
             f"{len(dpi_bypass_hosts)} dpi_bypass, {len(proxima_site_hosts)} proxima_sites)")


def write_host_vars(server: dict, include_ssh_pass: bool = False) -> None:
    """Generate inventory/host_vars/<name>.yml for a single server."""
    os.makedirs(HOST_VARS_DIR, exist_ok=True)

    data = {}
    data["server_ip"] = server["ip"]

    if server.get("node_id"):
        data["node_id"] = server["node_id"]

    # Decrypt credentials
    for field, key in [
        ("ss_password_enc", "ss_password"),
        ("agent_api_key_enc", "agent_api_key"),
        ("ssconf_token_enc", "ssconf_token"),
    ]:
        enc_val = server.get(field)
        if enc_val:
            dec_val = decrypt_value(enc_val)
            if dec_val:
                data[key] = dec_val

    # VPN exit specific
    if server["server_type"] == "vpn_exit" and server.get("install_adguard"):
        data["install_adguard"] = True

    # Include SSH password for provisioning (new servers)
    if include_ssh_pass and server.get("root_password_enc"):
        root_pass = decrypt_value(server["root_password_enc"])
        if root_pass:
            data["ansible_ssh_pass"] = root_pass

    path = os.path.join(HOST_VARS_DIR, f"{server['name']}.yml")
    content = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    _atomic_write(path, content)
    log.info(f"[INVENTORY] host_vars/{server['name']}.yml written")


def write_all_host_vars(servers: list[dict]) -> None:
    """Write host_vars for all servers."""
    for s in servers:
        if s["status"] == "decommissioned":
            continue
        include_ssh_pass = s["status"] == "provisioning"
        write_host_vars(s, include_ssh_pass=include_ssh_pass)


def remove_host_vars(name: str) -> None:
    """Remove host_vars file for a decommissioned server."""
    path = os.path.join(HOST_VARS_DIR, f"{name}.yml")
    if os.path.exists(path):
        os.remove(path)
        log.info(f"[INVENTORY] Removed host_vars/{name}.yml")


def write_vpn_server_host_vars(vpn_server: dict) -> None:
    """Credentials for a site server, written just before provisioning it.

    The SSH password is only present while the box is being claimed; once it
    has ADM's key the password is discarded from the database and stops
    appearing here.
    """
    os.makedirs(HOST_VARS_DIR, exist_ok=True)

    data = {}
    if vpn_server.get("server_code"):
        data["server_code"] = vpn_server["server_code"]

    enc = vpn_server.get("ssh_password_enc")
    if enc:
        password = decrypt_value(enc)
        if password:
            data["ansible_ssh_pass"] = password
            # Same secret for sudo: these boxes are installed with a single
            # admin account, so a separate become password would be fiction.
            if (vpn_server.get("ssh_user") or "root") != "root":
                data["ansible_become_password"] = password

    path = os.path.join(HOST_VARS_DIR, f"{vpn_server['name']}.yml")
    content = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    _atomic_write(path, content)
    log.info(f"[INVENTORY] host_vars/{vpn_server['name']}.yml written (site server)")


def regenerate_inventory() -> None:
    """Full regeneration: hosts.yml + all host_vars from DB."""
    servers = get_all_servers()
    write_hosts_yml(servers, get_all_vpn_servers())
    write_all_host_vars(servers)


def regenerate_for_server(server: dict, include_ssh_pass: bool = False) -> None:
    """Regenerate hosts.yml + this server's host_vars."""
    servers = get_all_servers()
    write_hosts_yml(servers, get_all_vpn_servers())
    write_host_vars(server, include_ssh_pass=include_ssh_pass)


def regenerate_for_vpn_server(vpn_server: dict) -> None:
    """Regenerate hosts.yml + this site server's host_vars."""
    write_hosts_yml(get_all_servers(), get_all_vpn_servers())
    write_vpn_server_host_vars(vpn_server)
