"""Midnight sticker-to-sticker reaction engine.

Replies to stickers with another sticker without requiring a reply to Midnight.
When Telegram exposes the source sticker's set, Midnight prefers that same pack;
otherwise it falls back to the real sticker IDs already present in the project.
"""
from __future__ import annotations

import logging
import random
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from handlers import chat as legacy_chat

log = logging.getLogger("midnight.stickers")


async def sticker_to_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not message.sticker:
        return
    if not legacy_chat.chat_enabled.get(str(chat.id), False):
        return

    incoming = message.sticker
    # Prefer the same sticker pack. This makes a sticker conversation feel like
    # an actual reaction rather than an unrelated random image.
    try:
        set_name = getattr(incoming, "set_name", None)
        if set_name:
            sticker_set = await context.bot.get_sticker_set(set_name)
            stickers = list(getattr(sticker_set, "stickers", ()) or ())
            candidates = [s for s in stickers if s.file_id != incoming.file_id]
            if candidates:
                chosen = random.choice(candidates)
                await message.reply_sticker(chosen.file_id)
                return
    except Exception as exc:
        log.debug("same-pack sticker lookup failed: %s", exc)

    # Fallback preserves the user's existing configured sticker IDs.
    stickers = getattr(legacy_chat, "SAMPLE_STICKERS", ())
    if stickers:
        try:
            await message.reply_sticker(legacy_chat._pick_sticker(str(chat.id)))
        except Exception as exc:
            log.info("sticker fallback failed: %s", exc)


def install(application) -> None:
    application.add_handler(
        MessageHandler(filters.Sticker.ALL, sticker_to_sticker),
        group=15,
    )
