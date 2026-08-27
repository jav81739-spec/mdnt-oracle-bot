"""Midnight Social Intelligence V2.

An original social layer: proactive but restrained, context-aware, playful,
and group-aware. It deliberately does not imitate any third-party bot.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters

from .storage import storage

TRIGGER_KEY = "midnight:trigger"
ROSTER_KEY = "midnight:roster"
ACTIVITY_KEY = "midnight:activity"
LAST_WAKE_KEY = "midnight:last_wake"

@dataclass(frozen=True)
class MemberSnapshot:
    user_id: int
    name: str
    username: str | None
    seen: float
    messages: int


def _safe_name(name: str) -> str:
    return re.sub(r"[<>]", "", name or "Midnight Soul").strip()[:80] or "Midnight Soul"


def _mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{_safe_name(name)}</a>'


def _key(chat_id: int, suffix: str) -> str:
    return f"{suffix}:{int(chat_id)}"


async def _touch(update: Update) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or user.is_bot or chat.type == "private":
        return
    roster = await storage.load(_key(chat.id, ROSTER_KEY), {})
    activity = await storage.load(_key(chat.id, ACTIVITY_KEY), {})
    if not isinstance(roster, dict): roster = {}
    if not isinstance(activity, dict): activity = {}
    uid = str(user.id)
    roster[uid] = {"user_id": int(user.id), "name": user.first_name or "Midnight Soul", "username": user.username, "seen": time.time()}
    activity[uid] = int(activity.get(uid, 0)) + 1
    cutoff = time.time() - 30 * 86400
    roster = {k: v for k, v in roster.items() if isinstance(v, dict) and float(v.get("seen", 0)) >= cutoff}
    activity = {k: v for k, v in activity.items() if k in roster}
    await storage.set(_key(chat.id, ROSTER_KEY), roster, ttl=35 * 86400)
    await storage.set(_key(chat.id, ACTIVITY_KEY), activity, ttl=35 * 86400)


async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await _touch(update)
    except Exception:
        pass


async def _snapshot(chat_id: int) -> list[MemberSnapshot]:
    roster = await storage.load(_key(chat_id, ROSTER_KEY), {})
    activity = await storage.load(_key(chat_id, ACTIVITY_KEY), {})
    if not isinstance(roster, dict): return []
    if not isinstance(activity, dict): activity = {}
    cutoff = time.time() - 7 * 86400
    result: list[MemberSnapshot] = []
    for key, raw in roster.items():
        try:
            seen = float(raw.get("seen", 0))
            if seen < cutoff: continue
            result.append(MemberSnapshot(int(raw["user_id"]), str(raw.get("name") or "Midnight Soul"), raw.get("username"), seen, int(activity.get(key, 0))))
        except (TypeError, ValueError, KeyError):
            continue
    return result


async def group_oracle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Midnight's lightweight understanding of the room."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("🌙 Group Oracle works inside a group chat.")
        return
    people = await _snapshot(chat.id)
    active = sorted(people, key=lambda p: (p.messages, p.seen), reverse=True)
    lines = [f"<b>☾ MIDNIGHT ROOM · {_safe_name(chat.title or 'Unknown')}</b>", "", f"Souls noticed: <b>{len(active)}</b>"]
    if active:
        lines.append("\n<b>Most present lately</b>")
        for p in active[:8]:
            lines.append(f"• {_mention(p.user_id, p.name)} · {p.messages} messages")
    lines.append("\n<i>Midnight tracks lightweight activity only; it does not expose private conversations or hidden member data.</i>")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


async def set_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("🌙 Set a Midnight trigger inside the group you want to awaken.")
        return
    word = (context.args[0].strip().lower() if context.args else "")
    if not word or len(word) > 32 or not re.fullmatch(r"[\w-]+", word, re.UNICODE):
        await update.effective_message.reply_text("Usage: /settrigger <word>\nExample: /settrigger midnight")
        return
    await storage.set(_key(chat.id, TRIGGER_KEY), word)
    await update.effective_message.reply_text(f"🌙 Trigger armed: <b>{_safe_name(word)}</b>\nSay it naturally and I'll know you're calling Midnight.", parse_mode="HTML")


async def trigger_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("🌙 Trigger info is group-specific.")
        return
    word = await storage.get(_key(chat.id, TRIGGER_KEY), "")
    await update.effective_message.reply_text(f"🌙 Current trigger: <b>{_safe_name(str(word))}</b>" if word else "🌙 No custom trigger is armed.", parse_mode="HTML")


async def trigger_listener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or user.is_bot or chat.type == "private": return
    text = message.text or message.caption or ""
    if not text: return
    trigger = str(await storage.get(_key(chat.id, TRIGGER_KEY), "") or "").strip().lower()
    if not trigger or not re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", text.lower()): return
    cooldown_key = _key(chat.id, LAST_WAKE_KEY)
    if await storage.get(cooldown_key, ""): return
    await storage.set(cooldown_key, "1", ttl=45)
    await message.reply_text("☾ <b>Midnight heard the call.</b>\nI'm here. What's happening? 🌙", parse_mode="HTML")


def install(application) -> None:
    application.add_handler(MessageHandler(filters.TEXT | filters.CaptionRegex(r"."), record_message), group=95)
    application.add_handler(MessageHandler(filters.TEXT | filters.CaptionRegex(r"."), trigger_listener), group=96)
    application.add_handler(CommandHandler("settrigger", set_trigger), group=-30)
    application.add_handler(CommandHandler("triggerinfo", trigger_info), group=-30)
    application.add_handler(CommandHandler("grouporacle", group_oracle), group=-30)
