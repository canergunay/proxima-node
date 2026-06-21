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
