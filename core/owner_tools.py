"""Private owner controls for Midnight's network and broadcasts.

The public bot never advertises these controls. Access is gated by a single
owner id supplied through the deployment environment, while durable chat
presence is recorded only for groups/channels where Midnight actually receives
updates.
"""
from __future__ import annotations

import os
import re
from typing import Any

from telegram import Update
from telegram.ext import ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .storage import storage

_CHAT_PREFIX = "midnight:chat:"
_OWNER_ENV_KEYS = ("MIDNIGHT_OWNER_ID", "OWNER_TELEGRAM_ID")
_COMMAND_RE = re.compile(r"^/[A-Za-z0-9_]+(?:@[A-Za-z0-9_]+)?")


def _owner_id() -> int | None:
    for key in _OWNER_ENV_KEYS:
        raw = os.getenv(key, "").strip()
        if raw:
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _key(chat_id: int) -> str:
    return f"{_CHAT_PREFIX}{int(chat_id)}"


def _is_owner(update: Update) -> bool:
    owner = _owner_id()
    user = update.effective_user
    return owner is not None and user is not None and int(user.id) == owner


async def _remember_chat(chat, *, active: bool = True) -> None:
    if chat is None or chat.type not in {"group", "supergroup", "channel"}:
        return
    previous = await storage.load(_key(chat.id), {})
    if not isinstance(previous, dict):
        previous = {}
    previous.update({
        "id": int(chat.id),
        "type": str(chat.type),
        "title": str(getattr(chat, "title", None) or previous.get("title") or "Untitled"),
        "username": getattr(chat, "username", None) or previous.get("username"),
        "active": bool(active),
    })
    await storage.set(_key(chat.id), previous)


async def remember_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _remember_chat(update.effective_chat, active=True)


async def remember_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.my_chat_member
    if change is None:
        return
    status = getattr(change.new_chat_member, "status", "")
    active = status not in {"left", "kicked"}
    await _remember_chat(update.effective_chat, active=active)


async def _authorized_or_silent(update: Update) -> bool:
    if _owner_id() is None:
        if update.effective_message:
            await update.effective_message.reply_text("🌘 Owner controls are not configured.")
        return False
    if not _is_owner(update):
        return False
    return True


def _broadcast_text(message) -> str:
    raw = message.text or ""
    match = _COMMAND_RE.match(raw)
    if not match:
        return ""
    # Deliberately slice instead of using context.args: this preserves every
    # space, newline, tab and Unicode character supplied after the command.
    return raw[match.end():].lstrip(" ")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_silent(update):
        return
    message = update.effective_message
    reply = message.reply_to_message if message else None
    text = _broadcast_text(message) if message else ""
    if not text and reply is None:
        await message.reply_text("Usage: /broadcast <message> — or reply to a message with /broadcast")
        return

    keys = await storage.scan(f"{_CHAT_PREFIX}*", count=250)
    sent = failed = 0
    stale: list[str] = []
    for key in keys:
        target = await storage.load(key, {})
        if not isinstance(target, dict) or not target.get("active"):
            continue
        chat_id = target.get("id")
        if not chat_id:
            continue
        try:
            if reply is not None and not text:
                await context.bot.copy_message(chat_id=int(chat_id), from_chat_id=message.chat_id, message_id=reply.message_id)
            else:
                await context.bot.send_message(chat_id=int(chat_id), text=text, disable_web_page_preview=True)
            sent += 1
        except Exception as exc:
            failed += 1
            error = str(exc).lower()
            if any(token in error for token in ("chat not found", "bot was kicked", "forbidden", "deactivated")):
                stale.append(key)

    for key in stale:
        target = await storage.load(key, {})
        if isinstance(target, dict):
            target["active"] = False
            await storage.set(key, target)

    await message.reply_text(f"🌙 Broadcast complete · {sent} delivered · {failed} unavailable")


async def network_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_silent(update):
        return
    keys = await storage.scan(f"{_CHAT_PREFIX}*", count=250)
    entries: list[dict[str, Any]] = []
    for key in keys:
        item = await storage.load(key, {})
        if isinstance(item, dict) and item.get("active"):
            entries.append(item)
    entries.sort(key=lambda item: (str(item.get("type")), str(item.get("title", "")).casefold()))

    groups = [x for x in entries if x.get("type") in {"group", "supergroup"}]
    channels = [x for x in entries if x.get("type") == "channel"]
    lines = ["🌙 <b>MIDNIGHT NETWORK</b>", ""]
    for label, items in (("GROUPS", groups), ("CHANNELS", channels)):
        lines.append(f"<b>{label} · {len(items)}</b>")
        for item in items:
            title = str(item.get("title") or "Untitled").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            username = item.get("username")
            link = f"https://t.me/{username}" if username else None
            lines.append(f"• {title}" + (f" — {link}" if link else " — private link"))
        lines.append("")
    lines.append(f"<b>TOTAL · {len(entries)}</b>")
    await message_or_reply(update, "\n".join(lines))


async def message_or_reply(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


def _remove_public_broadcast_handlers(application) -> None:
    for group, handlers in list(application.handlers.items()):
        kept = []
        for handler in handlers:
            commands = getattr(handler, "commands", None)
            if commands and ({"broadcast", "announce"} & set(commands)):
                continue
            kept.append(handler)
        application.handlers[group] = kept


def install(application) -> None:
    _remove_public_broadcast_handlers(application)
    application.add_handler(ChatMemberHandler(remember_membership, ChatMemberHandler.MY_CHAT_MEMBER), group=90)
    application.add_handler(MessageHandler(filters.ALL, remember_message), group=99)
    # Hidden from public command menus by design.
    application.add_handler(CommandHandler(["broadcast", "announce"], broadcast), group=-80)
    application.add_handler(CommandHandler("midnightmap", network_map), group=-79)
