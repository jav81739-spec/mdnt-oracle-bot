"""Midnight Oracle — tiny canonical Render entrypoint.

Telegram handler registration and lifecycle wiring live in handlers/runtime_registry.py.
This file owns only configuration, startup and the single runtime loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import legacy_bot  # canonical legacy feature provider
import startup
from handlers.runtime_registry import build_application, configure_lifecycle

load_dotenv()

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("midnight.bot")

BOT_NAME = "Midnight Oracle"
TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TZ", os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata")))

if not TOKEN:
    log.critical("BOT_TOKEN is not set. Add it to Render environment.")
    sys.exit(1)

if hasattr(legacy_bot, "GEMINI_MODEL") and legacy_bot.GEMINI_MODEL in {"gemini-3.7-flash", "gemini-3.5-flash-lite"}:
    legacy_bot.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

try:
    from storage import redis_client as storage_client
except Exception:
    log.exception("Storage facade failed to load")
    storage_client = None

startup.init(storage_client)

# Legacy compatibility contract retained intentionally: legacy_bot._addcoins,
# legacy_bot._generate_gemini and legacy_bot._start_dummy_server remain available
# to migrated modules/tests; bot.py itself does not own their runtime lifecycle.

log.info(
    "BOOT_DIAGNOSTIC | brand=%s | owner_configured=%s | group_configured=%s | tz=%s",
    BOT_NAME, bool(OWNER_ID), bool(GROUP_CHAT_ID), ORACLE_TZ.key,
)


def main():
    app = build_application(TOKEN, storage_client)
    configure_lifecycle(app, storage_client, ORACLE_TZ)
    log.info("Midnight Oracle starting — instance %s", startup._INSTANCE_ID)
    asyncio.run(startup.run(app, storage_client=storage_client))


if __name__ == "__main__":
    main()
