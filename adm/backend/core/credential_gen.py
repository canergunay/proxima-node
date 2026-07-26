"""Credential generation for new servers."""

import secrets


def gen_ss_password() -> str:
    return secrets.token_urlsafe(24)


def gen_agent_api_key() -> str:
    return secrets.token_urlsafe(36)


def gen_ssconf_token() -> str:
    return secrets.token_urlsafe(36)


def gen_node_id(hostname: str) -> str:
    return f"proxima-node-{hostname}"


# Ambiguous characters (0/O, 1/l/I) removed — these passwords are read off a
# screen and typed by hand into a VPN client.
_PWD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gen_vpn_user_password(length: int = 12) -> str:
    return "".join(secrets.choice(_PWD_ALPHABET) for _ in range(length))
