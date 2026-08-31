"""Private owner diagnostics and safe operational helpers for Midnight Oracle."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


def _owner_id() -> int:
    import os
    try:
        return int(os.getenv("OWNER_ID", "0"))
    except ValueError:
        return 0


def _private(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == _owner_id())


def _member_label(user: Any) -> str:
    username = getattr(user, "username", None)
    if username:
        return f"@{username}"
    name = getattr(user, "first_name", None) or getattr(user, "full_name", None) or "member"
    return str(name).replace("\n", " ")[:80]


async def owner_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private(update):
        return
    app = context.application
    data = getattr(app, "bot_data", {})
    started = data.get("oracle_started_at")
    await update.effective_message.reply_text(
        "☾ 𝐎𝐖𝐍𝐄𝐑 · 𝐎𝐑𝐀𝐂𝐋𝐄\n\n"
        f"Runtime: {'online' if started else 'online'}\n"
        f"Scheduler: {'ready' if getattr(app, 'job_queue', None) else 'unavailable'}\n"
        f"Known chats: {len(data.get('known_chats', {})) if isinstance(data.get('known_chats'), dict) else 0}\n"
        f"Checked: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )


async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private(update):
        return
    data = context.application.bot_data
    known = data.get("known_members", {})
    chats = data.get("known_chats", {})
    await update.effective_message.reply_text(
        "☾ 𝐎𝐑𝐀𝐂𝐋𝐄 · 𝐌𝐀𝐏\n\n"
        f"Known groups/chats: {len(chats) if isinstance(chats, dict) else 0}\n"
        f"Known members: {len(known) if isinstance(known, dict) else 0}\n"
        f"DM activity counter: {data.get('dm_activity', 0)}\n"
        f"Group activity counter: {data.get('group_activity', 0)}"
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("ownerstatus", owner_status), group=90)
    app.add_handler(CommandHandler("ownerstats", owner_stats), group=90)
