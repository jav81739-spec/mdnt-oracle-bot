"""Midnight Oracle owner-only /midnightmap command."""
from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.constants import ParseMode
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


async def _ensure_known_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, chat_type: str, title: str = ""):
    """Seed the registry from configured known chat IDs without changing chat data."""
    try:
        await startup.register_chat(chat_id=chat_id, chat_type=chat_type, title=title)
    except Exception as exc:
        log.debug("registry seed failed for %s: %s", chat_id, exc)


async def midnightmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not OWNER_ID or user.id != OWNER_ID:
        log.warning("/midnightmap denied: user_id=%s owner_configured=%s", getattr(user, "id", None), bool(OWNER_ID))
        return
    if message is None:
        return

    # A bot cannot ask Telegram for a universal "all chats I belong to" list.
    # Seed configured known target IDs so the map works even if those chats
    # have not produced a fresh update since the registry was introduced.
    configured = os.getenv("GROUP_CHAT_ID", "").strip()
    if configured:
        for raw_id in configured.split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            try:
                chat_id = int(raw_id)
                chat = await context.bot.get_chat(chat_id)
                await _ensure_known_chat(
                    context,
                    chat_id,
                    getattr(chat, "type", "group"),
                    getattr(chat, "title", "") or "",
                )
            except Exception as exc:
                log.warning("midnightmap: configured chat %s unavailable: %s", raw_id, exc)

    registry = await startup.get_chat_registry()
    if not registry:
        await message.reply_text(
            "🌙 Midnight Map\n\nNo groups or channels have been discovered yet.\n\n"
            "Telegram does not provide bots with a universal list of every chat they belong to. "
            "Add/observe a chat once, or configure its chat ID in GROUP_CHAT_ID."
        )
        return

    # Deliberately avoid Markdown parsing here: real group titles/user names can
    # contain Markdown characters and previously could make the entire reply fail.
    lines = ["🌙 MIDNIGHT MAP", "┄" * 18, "Known chats where Oracle has seen activity:", ""]

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
            where = f"ID: {chat_id}"

        lines.append(f"{title} · {chat_type}")
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

    lines.append("Only the owner can see this map. It reports known chats and known member activity.")
    await message.reply_text("\n".join(lines), disable_web_page_preview=True)
