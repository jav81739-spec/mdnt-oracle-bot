"""Small, additive runtime guards; never exposes Telegram identifiers publicly."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters


def _label(user) -> str:
    if getattr(user, "username", None):
        return f"@{user.username}"
    return (getattr(user, "first_name", None) or getattr(user, "full_name", None) or "member").replace("\n", " ")[:80]


async def observe_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return
    data = context.application.bot_data
    data["activity_events"] = int(data.get("activity_events", 0)) + 1
    members = data.setdefault("known_member_labels", {})
    # Internal key only; public responses must use _label(user), never this key.
    members[user.id] = _label(user)
    chats = data.setdefault("known_chat_labels", {})
    if chat.type in ("group", "supergroup", "channel"):
        chats[chat.id] = getattr(chat, "title", None) or _label(user)


def register(app: Application) -> None:
    app.add_handler(MessageHandler(filters.ALL, observe_activity), group=95)
