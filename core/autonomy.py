"""Autonomous social layer for Midnight Oracle V2.

The Oracle can create small, opt-in-by-presence group moments without requiring
members to know or invoke a command. It never chooses bots, never targets a
member repeatedly, and uses durable cooldowns so the feature feels rare rather
than spammy.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from .storage import Storage, storage

TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class Member:
    user_id: int
    name: str
    username: str | None
    seen: float


def _member_key(chat_id: int) -> str:
    return f"autonomy:members:{int(chat_id)}"


def _cooldown_key(chat_id: int) -> str:
    return f"autonomy:cooldown:{int(chat_id)}"


def _render_mention(member: Member) -> str:
    safe = member.name.replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={member.user_id}">{safe}</a>'


async def record_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Record recently active humans; installed as a low-priority message hook."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or user.is_bot or chat.type == "private":
        return

    members = await storage.load(_member_key(chat.id), {})
    if not isinstance(members, dict):
        members = {}
    members[str(user.id)] = {
        "user_id": int(user.id),
        "name": user.first_name or "Midnight Soul",
        "username": user.username,
        "seen": time.time(),
    }
    # Keep the activity pool compact and naturally self-pruning.
    cutoff = time.time() - 7 * 86400
    members = {k: v for k, v in members.items() if isinstance(v, dict) and float(v.get("seen", 0)) >= cutoff}
    await storage.set(_member_key(chat.id), members, ttl=8 * 86400)


async def _members(chat_id: int) -> list[Member]:
    raw = await storage.load(_member_key(chat_id), {})
    if not isinstance(raw, dict):
        return []
    cutoff = time.time() - 48 * 3600
    result: list[Member] = []
    for value in raw.values():
        try:
            seen = float(value["seen"])
            if seen < cutoff:
                continue
            result.append(Member(int(value["user_id"]), str(value.get("name") or "Midnight Soul"), value.get("username"), seen))
        except (KeyError, TypeError, ValueError):
            continue
    return result


async def _choose(chat_id: int, amount: int = 2) -> list[Member]:
    pool = await _members(chat_id)
    if len(pool) <= amount:
        return pool
    # Prefer recent activity, but retain randomness so the same people do not
    # become the permanent protagonists of the group.
    weights = [max(1.0, (m.seen - (time.time() - 48 * 3600)) / 3600 + 1) for m in pool]
    return random.choices(pool, weights=weights, k=amount) if amount == 1 else random.sample(pool, amount)


async def _already_busy(chat_id: int) -> bool:
    return bool(await storage.get(_cooldown_key(chat_id), ""))


async def _send(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)


async def _event(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    people = await _members(chat_id)
    if len(people) < 2:
        return False

    # Deliberately weighted toward lightweight social moments. Rare variants
    # make the system feel alive without turning every quiet period into spam.
    kind = random.choices(
        ["choice", "duo", "spotlight", "oracle_question", "duel", "midnight"],
        weights=[25, 22, 20, 18, 10, 5],
        k=1,
    )[0]
    selected = random.sample(people, 2)
    a, b = selected
    A, B = _render_mention(a), _render_mention(b)

    if kind == "choice":
        text = ("<b>✦ 𝐓𝐇𝐄 𝐎𝐑𝐀𝐂𝐋𝐄 𝐇𝐀𝐒 𝐂𝐇𝐎𝐒𝐄𝐍 ✦</b>\n\n"
                f"{A} × {B}\n\n<i>No nominations. No applications.\nThe night simply picked you two.</i> 🌙")
    elif kind == "duo":
        text = ("<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐃𝐔𝐎 ☽</b>\n\n"
                f"Tonight's unexpected pair: {A} + {B}\n\n"
                "<i>One conversation. One tiny mission. Make it interesting.</i> ✦")
    elif kind == "spotlight":
        target = random.choice(people)
        T = _render_mention(target)
        text = ("<b>⟡ 𝐓𝐎𝐍𝐈𝐆𝐇𝐓'𝐒 𝐒𝐏𝐎𝐓𝐋𝐈𝐆𝐇𝐓 ⟡</b>\n\n"
                f"{T}\n\n<i>The Oracle noticed you. That's all you're getting for now.</i> 🌘")
    elif kind == "oracle_question":
        target = random.choice(people)
        T = _render_mention(target)
        questions = [
            "What is one thing you would change about tonight?",
            "Who in this group has the most chaotic energy?",
            "What song belongs to this exact moment?",
            "Describe your current vibe in exactly three words.",
        ]
        text = ("<b>☽ 𝐎𝐑𝐀𝐂𝐋𝐄 𝐏𝐈𝐂𝐊𝐒 𝐀 𝐐𝐔𝐄𝐒𝐓𝐈𝐎𝐍 ☾</b>\n\n"
                f"{T}, {random.choice(questions)}\n\n<i>No pressure. Just answer if you feel like it.</i>")
    elif kind == "duel":
        text = ("<b>⚔️ 𝐓𝐖𝐎 𝐍𝐀𝐌𝐄𝐒. 𝐎𝐍𝐄 𝐑𝐎𝐔𝐍𝐃.</b>\n\n"
                f"{A} vs {B}\n\n<i>The group decides the category. The Oracle refuses to explain why.</i> 🌙")
    else:
        text = ("<b>𖤓 𝐀𝐅𝐓𝐄𝐑 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𖤓</b>\n\n"
                f"{A} and {B} have been quietly selected.\n\n"
                "<i>Something about this pairing felt interesting.</i> 🖤")

    await _send(chat_id, text, context)
    await storage.set(_cooldown_key(chat_id), "1", ttl=6 * 3600)
    return True


async def autonomous_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run rarely; each active chat gets an independent durable cooldown."""
    now = datetime.now(TZ)
    if now.hour < 9 and now.hour != 0:
        return
    keys = await storage.scan("autonomy:members:*", count=100)
    random.shuffle(keys)
    for key in keys[:30]:
        try:
            chat_id = int(key.rsplit(":", 1)[1])
        except (TypeError, ValueError):
            continue
        if await _already_busy(chat_id):
            continue
        # Only a small fraction of eligible ticks produce an event.
        if random.random() > 0.18:
            continue
        try:
            await _event(chat_id, context)
        except Exception:
            # Autonomous entertainment must never crash the bot.
            continue


def install(application) -> None:
    """Install the autonomous layer without interfering with command handlers."""
    # Import lazily so core remains lightweight in unit tests.
    from telegram.ext import MessageHandler, filters

    application.add_handler(MessageHandler(filters.ALL, record_activity), group=100)
    if application.job_queue is not None:
        application.job_queue.run_repeating(autonomous_tick, interval=20 * 60, first=90, name="oracle-autonomy")
