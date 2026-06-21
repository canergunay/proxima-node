"""First-boot import — populate DB from existing inventory files on ERG."""

import logging
import os

import yaml

from core.auth import encrypt_value
from core.config import REPO_ROOT
from core.db import create_server, server_count

log = logging.getLogger("adm.firstboot")

HOSTS_YML = os.path.join(REPO_ROOT, "inventory", "hosts.yml")
HOST_VARS_DIR = os.path.join(REPO_ROOT, "inventory", "host_vars")


def import_existing_servers() -> int:
    """Import servers from inventory files if DB is empty.

    Returns the number of servers imported.
    """
    if server_count() > 0:
        return 0

    if not os.path.exists(HOSTS_YML):
        log.info("[FIRSTBOOT] No hosts.yml found, skipping import")
        return 0

    with open(HOSTS_YML, "r") as f:
        inventory = yaml.safe_load(f) or {}

    children = inventory.get("all", {}).get("children", {})
    imported = 0

    for group_name, group_data in children.items():
        server_type = group_name  # "vpn_exit" or "dpi_bypass"
        hosts = group_data.get("hosts", {})

        for hostname, host_data in hosts.items():
            ip = host_data.get("ansible_host", "")
            location = host_data.get("server_location", "")
            provider = host_data.get("server_provider", "")

            if not ip:
                log.warning(f"[FIRSTBOOT] Skipping {hostname}: no ansible_host")
                continue

            # Try to read host_vars for credentials
            host_vars_path = os.path.join(HOST_VARS_DIR, f"{hostname}.yml")
            host_vars = {}
            if os.path.exists(host_vars_path):
                try:
                    with open(host_vars_path, "r") as f:
                        host_vars = yaml.safe_load(f) or {}
                except Exception as e:
                    log.warning(f"[FIRSTBOOT] Could not read host_vars for {hostname}: {e}")

            # Build display name
            loc_label = f" ({location})" if location else ""
            display_name = f"{hostname.upper()}{loc_label}"

            data = {
                "name": hostname,
                "display_name": display_name,
                "ip": ip,
                "server_type": server_type,
                "location": location,
                "provider": provider,
                "status": "active" if host_vars else "new",
                "node_id": host_vars.get("node_id"),
            }

            # Encrypt credentials if available
            for var_name, db_field in [
                ("ss_password", "ss_password_enc"),
                ("agent_api_key", "agent_api_key_enc"),
                ("ssconf_token", "ssconf_token_enc"),
            ]:
                val = host_vars.get(var_name)
                if val:
                    data[db_field] = encrypt_value(str(val))

            if host_vars.get("install_adguard"):
                data["install_adguard"] = True

            try:
                create_server(data)
                imported += 1
                log.info(f"[FIRSTBOOT] Imported {hostname} ({server_type}, {location or 'unknown'})")
            except Exception as e:
                log.error(f"[FIRSTBOOT] Failed to import {hostname}: {e}")

    log.info(f"[FIRSTBOOT] Imported {imported} servers from inventory")
    return imported
