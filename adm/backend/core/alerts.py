"""Telegram alert sender."""

import logging
import os

import requests

log = logging.getLogger("adm.alerts")

# Telegram API may be unreachable directly (e.g. from Russia).
# Set TELEGRAM_PROXY env var to route through a SOCKS proxy.
# Example: TELEGRAM_PROXY=socks5h://127.0.0.1:1081
_TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY", "")


def send_telegram(bot_token: str, chat_id: str, message: str) -> tuple[bool, str | None]:
    """Send a Telegram message via Bot API.

    Returns (success, error_message).
    """
    if not bot_token or not chat_id:
        return False, "Bot token or chat ID not configured"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    proxies = {"https": _TELEGRAM_PROXY, "http": _TELEGRAM_PROXY} if _TELEGRAM_PROXY else None
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=15,
            proxies=proxies,
        )
        data = resp.json()
        if data.get("ok"):
            return True, None
        return False, data.get("description", "Unknown Telegram error")
    except requests.exceptions.RequestException as e:
        log.error(f"Telegram send failed: {e}")
        return False, str(e)
