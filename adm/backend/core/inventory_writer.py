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
from core.db import get_all_servers

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


def write_hosts_yml(servers: list[dict]) -> None:
    """Generate inventory/hosts.yml from server list."""
    vpn_exit_hosts = {}
    dpi_bypass_hosts = {}

    for s in servers:
        if s["status"] == "decommissioned":
            continue
        host_entry = {"ansible_host": s["ip"]}
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

    content = yaml.dump(inventory, default_flow_style=False, sort_keys=False, allow_unicode=True)
    _atomic_write(HOSTS_YML, content)
    log.info(f"[INVENTORY] hosts.yml written ({len(vpn_exit_hosts)} vpn_exit, {len(dpi_bypass_hosts)} dpi_bypass)")


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
        ("speedtest_api_key_enc", "speedtest_api_key"),
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


def regenerate_inventory() -> None:
    """Full regeneration: hosts.yml + all host_vars from DB."""
    servers = get_all_servers()
    write_hosts_yml(servers)
    write_all_host_vars(servers)


def regenerate_for_server(server: dict, include_ssh_pass: bool = False) -> None:
    """Regenerate hosts.yml + this server's host_vars."""
    servers = get_all_servers()
    write_hosts_yml(servers)
    write_host_vars(server, include_ssh_pass=include_ssh_pass)
