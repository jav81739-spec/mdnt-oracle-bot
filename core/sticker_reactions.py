"""Midnight sticker-to-sticker reaction engine."""
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
    # Prefer the same sticker pack so a sticker conversation feels coherent.
    try:
        set_name = getattr(incoming, "set_name", None)
        if set_name:
            sticker_set = await context.bot.get_sticker_set(set_name)
            stickers = list(getattr(sticker_set, "stickers", ()) or ())
            candidates = [s for s in stickers if s.file_id != incoming.file_id]
            if candidates:
                await message.reply_sticker(random.choice(candidates).file_id)
                return
    except Exception as exc:
        log.debug("same-pack sticker lookup failed: %s", exc)

    # The project already carries the user's configured sticker IDs. Use the
    # existing picker directly; never call a helper that may not exist.
    try:
        sticker_id = legacy_chat._pick_sticker(str(chat.id))
        if sticker_id:
            await message.reply_sticker(sticker_id)
    except Exception:
        log.exception("configured sticker fallback failed")


def install(application) -> None:
    application.add_handler(
        MessageHandler(filters.Sticker.ALL, sticker_to_sticker),
        group=15,
    )
