"""Owner-only Midnight Oracle map.

Shows chats the bot has actually observed. Member names come from the durable
member tracker; Telegram does not expose a general 'list every member' API.
"""
from __future__ import annotations

import html
import json
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")


def _mention(m: dict) -> str:
    username = (m.get("username") or "").strip()
    if username:
        return f"@{html.escape(username)}"
    name = html.escape(m.get("name") or "Unknown")
    uid = int(m.get("id", 0) or 0)
    return f'<a href="tg://user?id={uid}">{name}</a>'


async def _load_members(storage, chat_id: int):
    if not storage:
        return []
    try:
        raw = storage.get(f"mbr:{chat_id}")
        if hasattr(raw, "__await__"):
            raw = await raw
        return json.loads(raw) if raw else []
    except Exception:
        return []


async def midnightmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        await update.message.reply_text("👁️ not for you.")
        return
    if update.effective_chat.type != "private":
        await update.message.reply_text("🌙 use /midnightmap in my DMs only.")
        return

    try:
        from startup import get_chat_registry
        from storage import redis_client
        registry = await get_chat_registry()
    except Exception:
        registry = {}
        redis_client = None

    if not registry:
        await update.message.reply_text(
            "🗺️ *MIDNIGHT MAP*\n\n"
            "No group/channel has been observed yet.\n"
            "Add me to a group and let me receive at least one update there.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["🗺️ *MIDNIGHT MAP*", "┄" * 18, ""]
    ordered = sorted(registry.items(), key=lambda item: item[1].get("seen", 0), reverse=True)

    for idx, (cid, info) in enumerate(ordered, 1):
        chat_id = int(cid)
        title = html.escape(info.get("title") or "Untitled chat")
        kind = info.get("type", "unknown")
        try:
            chat = await context.bot.get_chat(chat_id)
            title = html.escape(chat.title or title)
            username = getattr(chat, "username", None)
            public = f"https://t.me/{username}" if username else None
            count = await context.bot.get_chat_member_count(chat_id) if kind != "channel" else None
        except Exception:
            chat = None
            public = None
            count = None

        lines.append(f"*{idx}. {title}*")
        lines.append(f"`{kind}` · `{chat_id}`")
        if public:
            lines.append(f"🔗 {html.escape(public)}")
        else:
            lines.append("🔗 no public username · ID shown above")
        if count is not None:
            lines.append(f"👥 Telegram count: `{count}`")

        members = await _load_members(redis_client, chat_id)
        if members:
            members = sorted(members, key=lambda m: m.get("msgs", 0), reverse=True)
            lines.append("👤 *Tracked members:*")
            for member in members[:25]:
                lines.append(f"• {_mention(member)}")
            if len(members) > 25:
                lines.append(f"_…and {len(members) - 25} more tracked._")
        else:
            lines.append("👤 _No tracked members yet._")
        lines.append("")

    lines.append("┄" * 18)
    lines.append("_Map shows chats Midnight Oracle has actually observed._")
    lines.append("_For private chats, the numeric ID is the reliable locator._")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def register(app):
    app.add_handler(CommandHandler("midnightmap", midnightmap_command))
