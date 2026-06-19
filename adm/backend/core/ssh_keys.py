"""SSH key management — ensure ERG has a keypair and group_vars is configured."""

import logging
import os
import subprocess

import yaml

from core.config import REPO_ROOT

log = logging.getLogger("adm.ssh")

SSH_KEY_PATH = "/root/.ssh/id_ed25519"
SSH_PUBKEY_PATH = "/root/.ssh/id_ed25519.pub"
GROUP_VARS_ALL = os.path.join(REPO_ROOT, "inventory", "group_vars", "all.yml")


def ensure_ssh_key() -> str | None:
    """Ensure ERG has an SSH keypair. Returns the public key, or None if not on Linux."""
    if os.name != "posix":
        log.info("[SSH] Not on Linux, skipping SSH key check")
        return None

    # Check if key exists
    if not os.path.exists(SSH_KEY_PATH):
        log.info("[SSH] No SSH key found, generating ed25519 keypair...")
        os.makedirs(os.path.dirname(SSH_KEY_PATH), mode=0o700, exist_ok=True)
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", SSH_KEY_PATH, "-N", "", "-C", "proxima-adm"],
            check=True, capture_output=True,
        )
        log.info(f"[SSH] Generated keypair at {SSH_KEY_PATH}")

    # Read public key
    with open(SSH_PUBKEY_PATH, "r") as f:
        pubkey = f.read().strip()

    log.info(f"[SSH] Public key: {pubkey[:40]}...")
    return pubkey


def ensure_group_vars_ssh_key(pubkey: str) -> None:
    """Update group_vars/all.yml if ssh_public_key is still CHANGE_ME."""
    if not os.path.exists(GROUP_VARS_ALL):
        log.warning(f"[SSH] group_vars/all.yml not found at {GROUP_VARS_ALL}")
        return

    with open(GROUP_VARS_ALL, "r") as f:
        content = f.read()

    data = yaml.safe_load(content) or {}
    current_key = data.get("ssh_public_key", "")

    if "CHANGE_ME" in current_key:
        data["ssh_public_key"] = pubkey
        with open(GROUP_VARS_ALL, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        log.info("[SSH] Updated group_vars/all.yml with actual public key")
    elif current_key and current_key != pubkey:
        log.warning(f"[SSH] group_vars/all.yml has different key than {SSH_PUBKEY_PATH} — not overwriting")
    else:
        log.info("[SSH] group_vars/all.yml ssh_public_key is already set correctly")
