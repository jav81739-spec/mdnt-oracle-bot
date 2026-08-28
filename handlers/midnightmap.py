"""Midnight Oracle owner-only /midnightmap command."""
from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

import startup
from handlers.social_engine import _members

log = logging.getLogger("midnight.midnightmap")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")


def _mention(member: dict) -> str:
    username = (member.get("username") or "").strip()
    if username:
        return f"@{username}"
    return f"{member.get('name', 'Unknown')} (id={member.get('id')})"


async def midnightmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not OWNER_ID or user.id != OWNER_ID:
        return

    registry = await startup.get_chat_registry()
    if not registry:
        await update.effective_message.reply_text(
            "🌙 Midnight Map\n\nNo groups or channels have been discovered yet."
        )
        return

    lines = ["🌙 *MIDNIGHT MAP*", "┄" * 18, "_known chats where Oracle has seen activity:_", ""]

    for cid_text, info in sorted(registry.items(), key=lambda item: item[1].get("title", "").lower()):
        try:
            chat_id = int(cid_text)
        except (TypeError, ValueError):
            continue

        title = info.get("title") or "Untitled"
        chat_type = info.get("type") or "unknown"
        try:
            chat = await context.bot.get_chat(chat_id)
            title = getattr(chat, "title", None) or title
            username = getattr(chat, "username", None)
        except Exception as exc:
            log.debug("get_chat(%s) failed: %s", chat_id, exc)
            username = None

        if username:
            where = f"https://t.me/{username}"
        else:
            where = f"ID: `{chat_id}`"

        lines.append(f"*{title}* · `{chat_type}`")
        lines.append(f"  ↳ {where}")

        if chat_type in ("group", "supergroup"):
            members = await _members(chat_id)
            lines.append(f"  👥 Known members: {len(members)}")
            if members:
                for member in members:
                    lines.append(f"  • {_mention(member)}")
            else:
                lines.append("  • No member activity recorded yet.")
        elif chat_type == "channel":
            lines.append("  👥 Member list: not available from the channel registry")

        lines.append("")

    lines.append("_Only the owner can see this map. It reports known chats and known member activity; it does not expose hidden Telegram data._")
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
