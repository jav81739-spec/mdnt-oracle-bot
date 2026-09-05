"""Canonical live-chat bridge for Midnight Oracle.

This module deliberately contains no alternate AI implementation. It only connects
private Telegram text updates to the already-initialized MessageRouter. Group text
is routed by the canonical world/game lifecycle first, then by the primary router.
"""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger("midnight.live_chat")


async def handle_live_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or user.is_bot:
        return

    text = (message.text or message.caption or "").strip()
    if not text or text.startswith("/"):
        return

    # Group messages already have a canonical lifecycle handler in main.py.
    # Keeping this bridge private-only prevents it from running before games and
    # before the primary group router, which could otherwise produce double work.
    if chat.type != "private":
        return

    router = context.application.bot_data.get("oracle_router")
    if router is None:
        log.error(
            "LIVE_CHAT_ROUTER_MISSING | chat=%s | type=%s | user=%s",
            chat.id,
            chat.type,
            user.id,
        )
        return

    try:
        await router.handle(update, context)
    except Exception:
        # The router owns its own failure visibility. This final guard prevents
        # one malformed update from taking down the Telegram update loop.
        log.exception(
            "LIVE_CHAT_BRIDGE_FAILED | chat=%s | type=%s | user=%s",
            chat.id,
            chat.type,
            user.id,
        )
