"""Inline keyboard callbacks for lightweight social interactions."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledge a safe inline interaction and remove loading state."""
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
        value = (query.data or "").split(":", 1)
        if value[0] == "mood":
            await query.edit_message_text(f"☾ noted — {value[1] if len(value) > 1 else 'mood'}")
        elif value[0] == "truth":
            await query.answer("Passed. No explanation needed." if len(value) > 1 and value[1] == "pass" else "Take your time.", show_alert=False)
    except Exception:
        return
