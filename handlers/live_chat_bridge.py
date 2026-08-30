"""Canonical live-chat bridge for Midnight Oracle.

This module deliberately contains no alternate AI implementation. It only connects
Telegram's text updates to the already-initialized MessageRouter so DM, summoned
group chat, memory, cooldowns, media, achievements and the real AI generator all
share one path.
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

    if chat.type not in {"private", "group", "supergroup"}:
        return

    # Stateful game answers have their own handler. Do not let the general
    # conversational bridge also consume them and generate a second response.
    if chat.type in {"group", "supergroup"}:
        db = context.application.bot_data.get("oracle_db")
        if db is not None:
            try:
                row = await db.fetchone(
                    "SELECT state FROM game_sessions WHERE group_id=? AND game_type='word_scramble' AND is_active=1 ORDER BY id DESC LIMIT 1",
                    (int(chat.id),),
                )
                if row:
                    import json
                    state = json.loads(row[0])
                    if state.get("awaiting_answer"):
                        return
            except Exception:
                log.exception("GAME_ROUTING_GUARD_FAILED | chat=%s", chat.id)

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
