"""Durable utility features for Midnight Oracle v2.

This module owns restart-sensitive utility state instead of keeping it only in
Python process memory.  The public handler signatures stay compatible with the
existing Telegram registration so the command surface does not change.
"""
from __future__ import annotations

import json

from telegram import Update
from telegram.ext import ContextTypes

from .storage import storage

_AFK_TTL = 7 * 24 * 60 * 60


def _key(chat_id: int) -> str:
    return f"utility:afk:{int(chat_id)}"


async def _load(chat_id: int) -> dict[str, str]:
    raw = await storage.get(_key(chat_id), "{}")
    try:
        value = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (TypeError, ValueError):
        value = {}
    if not isinstance(value, dict):
        return {}
    return {str(uid): str(reason)[:500] for uid, reason in value.items()}


async def _save(chat_id: int, state: dict[str, str]) -> None:
    if state:
        await storage.set(_key(chat_id), state, ttl=_AFK_TTL)
    else:
        await storage.delete(_key(chat_id))


async def set_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    state = await _load(chat_id)
    reason = " ".join(context.args).strip() if context.args else "No reason given"
    state[str(user.id)] = reason[:500]
    await _save(chat_id, state)
    await update.message.reply_text(f"💤 {user.first_name} is now AFK: {reason[:500]}")


async def check_afk_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the sender's AFK state and announce AFK users when replied to."""
    message = update.message
    chat = update.effective_chat
    user = update.effective_user
    if message is None or chat is None or user is None:
        return

    state = await _load(chat.id)
    if not state:
        return

    own_key = str(user.id)
    if own_key in state:
        state.pop(own_key, None)
        await _save(chat.id, state)
        await message.reply_text(f"👋 Welcome back, {user.first_name}! AFK status cleared.")
        return

    reply = message.reply_to_message
    target = reply.from_user if reply else None
    if target is not None and str(target.id) in state:
        await message.reply_text(f"💤 {target.first_name} is AFK: {state[str(target.id)]}")
