"""Midnight Oracle — canonical Render entrypoint.

Telegram handler registration and lifecycle wiring live in handlers/runtime_registry.py.
This file owns configuration, startup and the single runtime loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load environment BEFORE importing modules that read configuration at import time.
load_dotenv()

import legacy_bot
import startup
from handlers.runtime_registry import build_application, configure_lifecycle

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

# Keep the model override compatible with the deployed Gemini endpoint.
# Do not resurrect known-retired model IDs even if an old Render env var exists.
if hasattr(legacy_bot, "GEMINI_MODEL"):
    configured_model = os.getenv("GEMINI_MODEL", "").strip()
    retired_models = {"gemini-2.0-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"}
    legacy_bot.GEMINI_MODEL = configured_model if configured_model and configured_model not in retired_models else "gemini-3.6-flash"
    log.info("AI_MODEL_SELECTED | model=%s", legacy_bot.GEMINI_MODEL)

# The legacy AI handler historically called this during provider failure, but
# some builds omitted the function. Install a provider-independent fallback so
# a Gemini outage can never turn into a NameError or a silent typing-only reply.
if not hasattr(legacy_bot, "_get_fallback_reply"):
    async def _get_fallback_reply(first_name="there"):
        name = (first_name or "there").strip()[:60]
        return f"{name} — give me that one again. I want to answer it properly. 🌙"
    legacy_bot._get_fallback_reply = _get_fallback_reply
    log.info("AI_FALLBACK_INSTALLED | provider_independent=true")

# Catch exceptions escaping the legacy AI handler. This is intentionally a thin
# wrapper: the original handler keeps all normal behavior and memory handling.
_original_ai_handler = getattr(legacy_bot, "handle_ai_message", None)
if _original_ai_handler is not None and not getattr(_original_ai_handler, "_resilient_wrapper", False):
    async def _resilient_ai_handler(update, context):
        try:
            return await _original_ai_handler(update, context)
        except Exception:
            user = getattr(update, "effective_user", None)
            name = getattr(user, "first_name", None) or "there"
            logger = logging.getLogger("midnight.ai")
            logger.exception("AI_HANDLER_FAILED | user=%s", name)
            try:
                chat = getattr(update, "effective_chat", None)
                if chat:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=await legacy_bot._get_fallback_reply(name),
                        disable_web_page_preview=True,
                    )
            except Exception:
                logger.exception("AI_FALLBACK_SEND_FAILED")
            return None
    _resilient_ai_handler._resilient_wrapper = True
    legacy_bot.handle_ai_message = _resilient_ai_handler

try:
    from storage import redis_client as storage_client
except Exception:
    log.exception("Storage facade failed to load")
    storage_client = None

startup.init(storage_client)

log.info(
    "BOOT_DIAGNOSTIC | brand=%s | owner_configured=%s | group_configured=%s | tz=%s",
    BOT_NAME, bool(OWNER_ID), bool(GROUP_CHAT_ID), ORACLE_TZ.key,
)


def _telegram_error_handler(update, context):
    log = logging.getLogger("midnight.telegram")
    log.exception("TELEGRAM_HANDLER_ERROR | update=%s", getattr(update, "update_id", "?"), exc_info=context.error)


def main():
    app = build_application(TOKEN, storage_client)
    app.add_error_handler(_telegram_error_handler)
    configure_lifecycle(app, storage_client, ORACLE_TZ)
    log.info("Midnight Oracle starting — instance %s", startup._INSTANCE_ID)
    asyncio.run(startup.run(app, storage_client=storage_client))


if __name__ == "__main__":
    main()
