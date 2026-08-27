"""Private owner controls for Midnight's network and broadcasts.

These controls intentionally stay out of the public command menu. The owner
can use them directly, while Midnight keeps a durable registry of chats it
actually observes or is explicitly added to.
"""
from __future__ import annotations

import os
import re
from typing import Any

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.ext import ChatMemberHandler, CommandHandler, ContextTypes, TypeHandler

from .storage import storage

_CHAT_PREFIX = "midnight:chat:"
_OWNER_ENV_KEYS = ("OWNER_TELEGRAM_ID", "MIDNIGHT_OWNER_ID")
_COMMAND_RE = re.compile(r"^/[A-Za-z0-9_]+(?:@[A-Za-z0-9_]+)?")


def _owner_id() -> int | None:
    """Use the existing owner setting; never require a second owner secret."""
    for key in _OWNER_ENV_KEYS:
        raw = os.getenv(key, "").strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _key(chat_id: int) -> str:
    return f"{_CHAT_PREFIX}{int(chat_id)}"


async def _remember_chat(chat, *, active: bool = True) -> None:
    if chat is None or chat.type not in {"group", "supergroup", "channel"}:
        return
    key = _key(chat.id)
    previous = await storage.load(key, {})
    if not isinstance(previous, dict):
        previous = {}
    previous.update(
        {
            "id": int(chat.id),
            "type": str(chat.type),
            "title": str(getattr(chat, "title", None) or previous.get("title") or "Untitled"),
            "username": getattr(chat, "username", None) or previous.get("username"),
            "active": bool(active),
        }
    )
    await storage.set(key, previous)


async def remember_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Observe every Telegram update without interfering with normal handlers."""
    try:
        chat = update.effective_chat
        if chat is not None:
            await _remember_chat(chat, active=True)
    except Exception:
        return


async def remember_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.my_chat_member
    if change is None:
        return
    status = getattr(change.new_chat_member, "status", "")
    active = status not in {"left", "kicked"}
    await _remember_chat(update.effective_chat, active=active)


async def _authorized_or_silent(update: Update) -> bool:
    owner = _owner_id()
    user = update.effective_user
    return owner is not None and user is not None and int(user.id) == owner


def _broadcast_text(message) -> str:
    raw = message.text or ""
    match = _COMMAND_RE.match(raw)
    if not match:
        return ""
    return raw[match.end() :].lstrip(" ")


async def _active_targets() -> list[dict[str, Any]]:
    keys = await storage.scan(f"{_CHAT_PREFIX}*", count=250)
    targets: list[dict[str, Any]] = []
    for key in keys:
        item = await storage.load(key, {})
        if isinstance(item, dict) and item.get("active") and item.get("id"):
            targets.append(item)
    return targets


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_silent(update):
        return
    message = update.effective_message
    if message is None:
        return

    reply = message.reply_to_message
    text = _broadcast_text(message)
    if not text and reply is None:
        await message.reply_text("Usage: /broadcast <message> — or reply to a message with /broadcast")
        return

    targets = await _active_targets()
    sent = failed = 0
    stale: list[str] = []

    for target in targets:
        chat_id = int(target["id"])
        try:
            if reply is not None and not text:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=message.chat_id,
                    message_id=reply.message_id,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=True,
                )
            sent += 1
        except Exception as exc:
            failed += 1
            error = str(exc).lower()
            if any(token in error for token in ("chat not found", "bot was kicked", "forbidden", "deactivated", "have no rights")):
                stale.append(_key(chat_id))

    for key in stale:
        target = await storage.load(key, {})
        if isinstance(target, dict):
            target["active"] = False
            await storage.set(key, target)

    await message.reply_text(f"🌙 Broadcast complete · {sent} delivered · {failed} unavailable")


async def network_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_silent(update):
        return

    entries = await _active_targets()
    entries.sort(key=lambda item: (str(item.get("type")), str(item.get("title", "")).casefold()))
    groups = [x for x in entries if x.get("type") in {"group", "supergroup"}]
    channels = [x for x in entries if x.get("type") == "channel"]

    lines = ["🌙 <b>MIDNIGHT NETWORK</b>", ""]
    for label, items in (("GROUPS", groups), ("CHANNELS", channels)):
        lines.append(f"<b>{label} · {len(items)}</b>")
        for item in items:
            title = str(item.get("title") or "Untitled").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            username = str(item.get("username") or "").lstrip("@")
            link = f"https://t.me/{username}" if username else None
            lines.append(f"• {title}" + (f" — {link}" if link else " — private link"))
        lines.append("")
    lines.append(f"<b>TOTAL · {len(entries)}</b>")

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def publish_owner_menu(application) -> None:
    """Publish the private controls only to the configured owner chat."""
    owner = _owner_id()
    if owner is None:
        return
    commands = [
        BotCommand("broadcast", "Send a private Midnight broadcast"),
        BotCommand("announce", "Send a private Midnight announcement"),
        BotCommand("midnightmap", "View Midnight's private network map"),
    ]
    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=owner))
    except Exception:
        # A command-menu failure must never prevent the bot from starting.
        return


def _remove_public_broadcast_handlers(application) -> None:
    """Remove duplicate legacy broadcast registrations before adding ours."""
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
    application.add_handler(TypeHandler(Update, remember_update), group=-1000)
    application.add_handler(
        ChatMemberHandler(remember_membership, ChatMemberHandler.MY_CHAT_MEMBER),
        group=-999,
    )
    application.add_handler(CommandHandler(["broadcast", "announce"], broadcast), group=-80)
    application.add_handler(CommandHandler("midnightmap", network_map), group=-79)
