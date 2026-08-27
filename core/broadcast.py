"""Safe, durable owner broadcast for Midnight Oracle.

The broadcaster never deletes or rewrites existing recipient data. It keeps its
own registry and lazily migrates group/channel ids that are already present in
Redis key names. Failed destinations are retained and marked unavailable so a
future interaction can reactivate them.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from telegram import Update
from telegram.constants import ChatType
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from .storage import storage

log = logging.getLogger("midnight.broadcast")
_REGISTRY = "midnight:broadcast:recipients:v1"
_LOCK = "midnight:broadcast:lock"
_CHAT_ID_RE = re.compile(r"(?<!\d)-100\d{5,15}(?!\d)")
_OWNER_KEYS = ("OWNER_ID", "OWNER_USER_ID", "TELEGRAM_OWNER_ID")


def _owner_ids() -> set[int]:
    values: set[int] = set()
    for name in _OWNER_KEYS:
        raw = os.getenv(name, "")
        for part in raw.replace(";", ",").split(","):
            try:
                if part.strip():
                    values.add(int(part.strip()))
            except ValueError:
                continue
    return values


def _is_owner(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in _owner_ids())


async def _save_recipient(chat_id: int, chat_type: str) -> None:
    if chat_type not in {ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}:
        return
    current = await storage.load(_REGISTRY, {})
    if not isinstance(current, dict):
        current = {}
    current[str(int(chat_id))] = {"type": str(chat_type), "active": True}
    await storage.save(_REGISTRY, current)


async def _discover_legacy_chats() -> set[int]:
    """Recover group/channel ids without touching or deleting legacy keys."""
    ids: set[int] = set()
    try:
        for key in await storage.scan("*", count=250):
            for match in _CHAT_ID_RE.findall(str(key)):
                try:
                    ids.add(int(match))
                except ValueError:
                    pass
    except Exception:
        log.exception("Legacy recipient discovery failed")
    return ids


async def _recipients() -> dict[int, dict[str, Any]]:
    current = await storage.load(_REGISTRY, {})
    if not isinstance(current, dict):
        current = {}
    changed = False
    for chat_id in await _discover_legacy_chats():
        key = str(chat_id)
        if key not in current:
            current[key] = {"type": "group_or_channel", "active": True, "legacy": True}
            changed = True
    if changed:
        await storage.save(_REGISTRY, current)
    return {int(k): v for k, v in current.items() if str(k).lstrip("-").isdigit()}


async def _remember_update(update: Update) -> None:
    chat = update.effective_chat
    if chat is not None:
        await _save_recipient(chat.id, chat.type)


async def _track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await _remember_update(update)
    except Exception:
        log.exception("Recipient tracking failed")


async def _track_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await _remember_update(update)
    except Exception:
        log.exception("Membership tracking failed")


async def _broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    message = update.effective_message
    if message is None:
        return

    # Preferred mode: reply to any Telegram message and /broadcast it.
    source = message.reply_to_message
    text = " ".join(context.args).strip()
    if source is None and not text:
        await message.reply_text("Reply to a message with /broadcast, or use /broadcast <text>.")
        return

    async with storage.lock(_LOCK, ttl=600, wait=2.0) as acquired:
        if not acquired:
            await message.reply_text("🌙 Another broadcast is already running.")
            return

        recipients = await _recipients()
        delivered = unavailable = 0
        total = len(recipients)
        for chat_id, meta in recipients.items():
            try:
                if source is not None:
                    await source.copy(chat_id)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                delivered += 1
                meta["active"] = True
                meta["last_ok"] = True
            except RetryAfter as exc:
                await asyncio.sleep(float(exc.retry_after) + 0.5)
                try:
                    if source is not None:
                        await source.copy(chat_id)
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=text)
                    delivered += 1
                    meta["active"] = True
                except TelegramError:
                    unavailable += 1
                    meta["active"] = False
            except (Forbidden, TelegramError):
                unavailable += 1
                # Keep the destination in the registry: never delete old groups/channels.
                meta["active"] = False
            except Exception:
                unavailable += 1
                meta["active"] = False
                log.exception("Broadcast failed for chat=%s", chat_id)

        await storage.save(_REGISTRY, {str(k): v for k, v in recipients.items()})
        await message.reply_text(
            f"🌙 Broadcast complete · {delivered} delivered · {unavailable} unavailable · {total} destinations"
        )


def install(application) -> None:
    """Install broadcast/tracking handlers exactly once."""
    if getattr(application, "_midnight_broadcast_installed", False):
        return
    application._midnight_broadcast_installed = True
    application.add_handler(CommandHandler("broadcast", _broadcast), group=-20)
    application.add_handler(MessageHandler(filters.ALL, _track_message), group=100)
    log.info("BROADCAST handlers installed")


__all__ = ["install"]
