"""Midnight Oracle — Relationship Ritual Engine.

Command-driven social readings. This layer is intentionally separate from the
scheduled Social Engine; it quietly records interaction signals that scheduled
Oracle features may use later without exposing the implementation relationship.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from . import social_engine

PREFIX = "oracle:rel:"
LOCK_SECONDS = 24 * 60 * 60


def _state(app):
    return app.bot_data.setdefault("oracle_relationships", {})


def _pair_key(chat_id: int, a: int, b: int) -> str:
    x, y = sorted((int(a), int(b)))
    return f"{PREFIX}{chat_id}:{x}:{y}"


def _member_from_token(members, token: str):
    token = token.strip().lstrip("@").lower()
    for m in members:
        if str(m.get("id")) == token or str(m.get("username", "")).lower() == token:
            return m
    return None


async def _targets(update: Update):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return None, None, None
    members = await social_engine._members(chat.id)
    args = list(getattr(update, "effective_message", None) and [])
    # Context args are supplied by the command handlers below.
    return chat, user, members


def _resolve(update: Update, context: ContextTypes.DEFAULT_TYPE, members):
    msg = update.effective_message
    actor = update.effective_user
    first = _member_from_token(members, context.args[0]) if context.args else None
    second = _member_from_token(members, context.args[1]) if len(context.args) > 1 else None
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        replied = msg.reply_to_message.from_user
        second = second or _member_from_token(members, str(replied.id))
        first = first or _member_from_token(members, str(actor.id))
    if first is None:
        first = _member_from_token(members, str(actor.id))
    if second is None and len(context.args) == 1:
        second = _member_from_token(members, context.args[0])
    if second is None or first is None or first["id"] == second["id"]:
        return None, None
    return first, second


def _ensure(pair):
    pair.setdefault("familiarity", 0)
    pair.setdefault("trust", 0)
    pair.setdefault("affinity", 0)
    pair.setdefault("tension", 0)
    pair.setdefault("momentum", 0)
    pair.setdefault("attention", 0)
    pair.setdefault("chaos", 0)
    pair.setdefault("distance", 0)
    pair.setdefault("uses", 0)
    return pair


def _mention(m):
    u = m.get("username")
    return f"@{u}" if u else f"[{m.get('name','someone')}](tg://user?id={m['id']})"


def _score(seed, lo=42, hi=94):
    return lo + (int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (hi - lo + 1))


def _reading(kind, a, b, state):
    key = f"{kind}:{a['id']}:{b['id']}:{state.get('uses', 0)}"
    score = _score(key)
    pairs = f"{_mention(a)} × {_mention(b)}"
    lines = {
        "thread": ("THREAD OPEN", f"A line keeps appearing between {pairs}. Not loud. Not accidental."),
        "orbit": ("ORBIT TRACE", f"{pairs} keep returning to the same conversational gravity. The pattern is stronger than the noise."),
        "echo": ("ECHO FOUND", f"{pairs} reflect something in each other that neither one seems to name directly."),
        "tether": ("TETHER READING", f"{pairs} have a connection that survives ordinary distance. The Oracle marked the thread."),
        "rift": ("RIFT READING", f"{pairs} carry a little unfinished tension. Distance is not always the opposite of connection."),
        "spark": ("SPARK TRACE", f"{pairs} produce an unusual amount of attention when their paths cross."),
        "mirror": ("MIRROR READING", f"{pairs} keep reflecting opposite sides of the same room. One reveals the other."),
        "crossing": ("CROSSING", f"The paths of {pairs} cross more often than chance would make interesting."),
        "undertow": ("UNDERTOW", f"There is a quiet pull beneath {pairs}. The surface is not the whole story."),
        "verdict": ("ORACLE VERDICT", f"{pairs}: the connection is real inside the Oracle's records. Its name is deliberately withheld."),
    }
    title, body = lines[kind]
    return f"☾ *{title}*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{body}\n\n`✦` {_mention(a)}\n`✦` {_mention(b)}\n\n*signal · {score}%*\n\n_The Oracle records patterns. It does not explain them._\n\n🌙 *— Midnight Oracle*"


async def _ritual(kind, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user, members = await _targets(update)
    if not chat:
        return
    a, b = _resolve(update, context, members)
    if not a or not b:
        await update.effective_message.reply_text(f"☾ Use /{kind} @member @member — or reply to a member.")
        return
    state = _state(context.application)
    key = _pair_key(chat.id, a["id"], b["id"])
    pair = _ensure(state.setdefault(key, {}))
    pair["uses"] += 1
    now = int(time.time())
    pair["last"] = now
    deltas = {
        "thread": (2, 2, 3, 0, 3, 1, 0, -1),
        "orbit": (3, 1, 2, 0, 4, 3, 0, -1),
        "echo": (4, 2, 2, 0, 3, 2, 0, -1),
        "tether": (3, 4, 4, 0, 2, 2, 0, -2),
        "rift": (1, 0, 0, 5, 1, 1, 1, 3),
        "spark": (2, 1, 5, 0, 3, 4, 2, -1),
        "mirror": (3, 3, 3, 1, 2, 2, 0, 0),
        "crossing": (3, 2, 3, 0, 4, 3, 1, -1),
        "undertow": (2, 2, 5, 1, 3, 4, 1, -2),
        "verdict": (2, 2, 2, 0, 2, 2, 0, -1),
    }[kind]
    for field, delta in zip(("familiarity", "trust", "affinity", "tension", "momentum", "attention", "chaos", "distance"), deltas):
        pair[field] = max(0, min(100, pair[field] + delta))
    await update.effective_message.reply_text(_reading(kind, a, b, pair), parse_mode="Markdown", disable_web_page_preview=True)


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user, members = await _targets(update)
    if not chat: return
    a, b = _resolve(update, context, members)
    if not a or not b:
        await update.effective_message.reply_text("☾ Use /watch @member @member — or reply to a member."); return
    key = _pair_key(chat.id, a["id"], b["id"])
    pair = _ensure(_state(context.application).setdefault(key, {}))
    pair["watch"] = True
    pair["watch_since"] = int(time.time())
    await update.effective_message.reply_text(f"👁️ *WATCH ESTABLISHED*\n\n{_mention(a)} × {_mention(b)}\n\n_The Oracle will keep this thread in its peripheral vision. It will not explain when it notices something._", parse_mode="Markdown")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat, user, members = await _targets(update)
    if not chat: return
    a, b = _resolve(update, context, members)
    if not a or not b:
        await update.effective_message.reply_text("☾ Use /unwatch @member @member — or reply to a member."); return
    key = _pair_key(chat.id, a["id"], b["id"])
    pair = _ensure(_state(context.application).setdefault(key, {}))
    pair["watch"] = False
    await update.effective_message.reply_text("☾ *WATCH RELEASED*\n\n_The Oracle has stopped actively observing this thread._", parse_mode="Markdown")


async def sealed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The 24-hour locked ritual: intentionally rare and visibly countdown-based."""
    chat, user, members = await _targets(update)
    if not chat: return
    a, b = _resolve(update, context, members)
    if not a or not b:
        await update.effective_message.reply_text("☾ Use /sealed @member @member — or reply to a member."); return
    state = _state(context.application)
    key = _pair_key(chat.id, a["id"], b["id"]) + ":sealed"
    now = int(time.time())
    until = int(state.get(key, 0) or 0)
    if until > now:
        remaining = timedelta(seconds=until - now)
        total_hours = remaining.total_seconds() / 3600
        await update.effective_message.reply_text(
            f"🔒 *SEALED*\n\n{_mention(a)} × {_mention(b)}\n\n_This reading is still sealed._\n\n**{total_hours:.1f} hours remaining**\n\n_The Oracle will not open it early._", parse_mode="Markdown")
        return
    state[key] = now + LOCK_SECONDS
    pair = _ensure(state.setdefault(_pair_key(chat.id, a["id"], b["id"]), {}))
    pair["sealed_at"] = now
    pair["sealed_until"] = state[key]
    await update.effective_message.reply_text(
        f"🔒 *THE SEALED HOUR*\n\n{_mention(a)} × {_mention(b)}\n\n_The Oracle found something it refuses to reveal yet._\n\n**24 hours remaining.**\n\n_Do not ask again. The lock is part of the reading._\n\n🌙 *— Midnight Oracle*", parse_mode="Markdown")


COMMANDS = {
    "thread": "thread", "orbit": "orbit", "echo": "echo", "tether": "tether",
    "rift": "rift", "spark": "spark", "mirror": "mirror", "crossing": "crossing",
    "undertow": "undertow", "verdict": "verdict",
}


def register(app: Application):
    existing = {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}
    for command, kind in COMMANDS.items():
        if command not in existing:
            async def handler(update, context, _kind=kind):
                await _ritual(_kind, update, context)
            app.add_handler(CommandHandler(command, handler), group=0)
    if "watch" not in existing:
        app.add_handler(CommandHandler("watch", watch), group=0)
    if "unwatch" not in existing:
        app.add_handler(CommandHandler("unwatch", unwatch), group=0)
    if "sealed" not in existing:
        app.add_handler(CommandHandler("sealed", sealed), group=0)
