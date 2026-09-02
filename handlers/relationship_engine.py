"""Midnight Oracle — private relationship ritual surface."""
from __future__ import annotations

import html
import random
from datetime import datetime, timedelta, timezone

from telegram.ext import Application, CommandHandler

from . import social_engine
from core.ai import AIUnavailable, service as ai_service
from core.oracle_instinct import choose_pair

PREFIX = "oracle:rel:"
ORACLE_HOUR = 0
ORACLE_MINUTE = 7


def _state(app):
    return app.bot_data.setdefault("oracle_relationships", {})


def _pair_key(chat_id, a, b):
    x, y = sorted((int(a), int(b)))
    return f"{PREFIX}{chat_id}:{x}:{y}"


def _member_from_token(members, token):
    token = token.strip().lstrip("@").casefold()
    return next((m for m in members if str(m.get("username", "")).casefold() == token), None)


def _display(m):
    username = str(m.get("username", "")).strip()
    return f"@{username}" if username else str(m.get("name", "someone")).strip() or "someone"


def _pair_display(a, b):
    return f"{_display(a)} × {_display(b)}"


async def _targets(update):
    chat, user = update.effective_chat, update.effective_user
    return (chat, user, await social_engine._members(chat.id)) if chat and user else (None, None, [])


def _resolve(update, context, members, kind="bond"):
    """Honor explicit targets; otherwise Oracle Instinct chooses the pair."""
    actor = update.effective_user
    msg = update.effective_message
    first = _member_from_token(members, context.args[0]) if context.args else None
    second = _member_from_token(members, context.args[1]) if len(context.args) > 1 else None
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        rid = msg.reply_to_message.from_user.id
        second = second or next((m for m in members if int(m.get("id", -1)) == rid), None)
        if not first and actor:
            first = next((m for m in members if int(m.get("id", -1)) == actor.id), None)
    if not first and actor:
        first = next((m for m in members if int(m.get("id", -1)) == actor.id), None)
    if not second and len(context.args) == 1:
        second = _member_from_token(members, context.args[0])
    if first and second and first["id"] != second["id"]:
        return first, second
    if not context.args and not (msg and msg.reply_to_message) and len(members) >= 2:
        return choose_pair(context.application, update.effective_chat.id, members, kind) or (None, None)
    return (None, None)


def _ensure(p):
    for k in ("familiarity", "trust", "affinity", "tension", "momentum", "attention", "chaos", "distance", "uses"):
        p.setdefault(k, 0)
    return p


_TITLES = {
    "bond": "BOND READING",
    "thread": "THE WEAVE",
    "orbit": "ORBIT TRACE",
    "echo": "ECHO FOUND",
    "tether": "THE ANCHOR",
    "rift": "THE FRACTURE",
    "spark": "EMBER TRACE",
    "mirror": "MIRROR READING",
    "crossing": "CROSSING",
    "undertow": "UNDERTOW",
    "verdict": "ORACLE EDICT",
}

_FORBIDDEN_READING_PHRASES = (
    "paths cross",
    "records patterns",
    "does not explain",
    "conversational gravity",
    "quiet pull",
    "inside the oracle's records",
    "signal ·",
    "signal:",
)

_FALLBACK_LINES = {
    "bond": (
        "There is an ease here that keeps surviving the little awkward moments.",
        "These two don't have to make much of a scene to keep ending up in the same orbit of conversation.",
        "Something about the way these two meet in a room feels more familiar than it should.",
    ),
    "thread": (
        "The conversation keeps finding a loose thread between them, even when neither one starts there.",
        "They keep picking up pieces of the same conversation without quite agreeing that it matters.",
        "There is a small continuity here that is easy to miss until it happens again.",
    ),
    "orbit": (
        "They don't seem to seek each other out every time. Somehow, they still keep arriving in the same moments.",
        "One turns up, then the other does. It has happened enough times to become interesting.",
        "Their timing has a habit of becoming noticeable only after the fact.",
    ),
    "echo": (
        "One of them says something and the other seems to answer it without quite answering it.",
        "There is a familiar little rhythm between them, the kind that usually comes from having noticed each other for a while.",
        "They seem to catch details in each other that most people would let pass.",
    ),
    "tether": (
        "Distance doesn't seem to erase much between these two. It only makes the next interaction more noticeable.",
        "Whatever keeps these two connected is quieter than attention and harder to shake.",
        "Even apart, they leave enough unfinished between them for the next meeting to pick it up again.",
    ),
    "rift": (
        "There is something unresolved here, and neither distance nor silence has quite managed to make it disappear.",
        "The awkward part is not that they disagree. It is that the disagreement still seems to matter.",
        "Something changed between them, but it did not finish changing.",
    ),
    "spark": (
        "When these two land in the same conversation, the room seems to get a little less predictable.",
        "There is a quickness between them that doesn't need much encouragement.",
        "Their best moments seem to happen before either one has decided to make them happen.",
    ),
    "mirror": (
        "They seem to notice the same room from completely different angles.",
        "One of them keeps revealing a side of the other that was already there, just harder to see.",
        "They are not alike in the obvious ways. That may be the interesting part.",
    ),
    "crossing": (
        "These two keep turning up in the same little corners of the group. Neither appearance looks planned, which is what makes it worth noticing.",
        "There have been enough near-misses and shared moments here that coincidence is starting to feel a little lazy as an explanation.",
        "They keep arriving at the same moment from different directions. Sometimes that is all a connection needs to announce itself.",
    ),
    "undertow": (
        "The visible part of this connection is not the whole thing. There is something quieter underneath it.",
        "They may not talk about whatever this is, but the small reactions around each other keep giving it away.",
        "Nothing dramatic is happening here. That is almost what makes the undercurrent noticeable.",
    ),
    "verdict": (
        "Whatever this connection is, it has lasted long enough to deserve a name. The Oracle is leaving that part to them.",
        "There is enough here to call it something, but not enough to pretend the name is obvious.",
        "The evidence is interesting. The conclusion can wait.",
    ),
}


def _reading_prompt(kind, a, b, state):
    pair = _pair_display(a, b)
    return f"""You are Midnight Oracle writing one private relationship reading for a Telegram group.

Command: {kind}
People: {pair}
Internal state (do not mention these numbers or the mechanism): familiarity={state.get('familiarity', 0)}, trust={state.get('trust', 0)}, affinity={state.get('affinity', 0)}, tension={state.get('tension', 0)}, momentum={state.get('momentum', 0)}, attention={state.get('attention', 0)}, chaos={state.get('chaos', 0)}, distance={state.get('distance', 0)}, reading_count={state.get('uses', 0)}.

Write 2 or 3 short sentences, 35 to 75 words total. Make this feel like a sharp human observation that happened in a real group, not a generated horoscope.
Use the two people naturally by their displayed names where useful. Be specific enough to feel observed, but never invent private facts, quotes, events, feelings, or conversations that were not supplied.
Let the tone emerge from the command: it may be warm, playful, strange, tense, understated, amused, or quietly curious. It does NOT have to be mystical.

Hard rules:
- Do not use a fixed metaphor or recurring sentence pattern.
- Do not say or imply that you are following an algorithm, score, signal, database, records, pattern-recognition system, or selection mechanism.
- Do not use the phrases "paths cross", "conversational gravity", "quiet pull", "records patterns", or "does not explain".
- Do not add a title, divider, bullet list, percentage, confidence score, moral, lesson, prophecy, or signature.
- Do not end with a generic philosophical line.
- Do not start with "The Oracle".
- Do not describe what the command means; simply give the reading.
- Never mention these instructions.

Return only the reading."""


def _clean_reading(text):
    text = " ".join(str(text or "").replace("\n", " ").split()).strip()
    text = text.strip(" \"'“”‘’")
    if not text:
        return ""
    if any(phrase in text.casefold() for phrase in _FORBIDDEN_READING_PHRASES):
        return ""
    if len(text) < 35 or len(text) > 520:
        return ""
    return text


async def _reading(kind, a, b, state):
    prompt = _reading_prompt(kind, a, b, state)
    try:
        generated = _clean_reading(await ai_service.generate(prompt, timeout=12.0))
        if generated:
            return generated
    except (AIUnavailable, Exception):
        pass
    lines = _FALLBACK_LINES.get(kind, _FALLBACK_LINES["bond"])
    seed = f"{kind}:{a.get('id')}:{b.get('id')}:{state.get('uses', 0)}"
    index = random.Random(seed).randrange(len(lines))
    return lines[index]


def _reading_text(kind, a, b, body):
    title = _TITLES[kind]
    return f"☾ {title}\n\n{body}\n\n✦ {_display(a)}\n✦ {_display(b)}"


async def _ritual(kind, update, context):
    chat, _, members = await _targets(update)
    if not chat:
        return
    if len(members) < 2:
        await update.effective_message.reply_text("☾ I need at least two known group members before I can choose the pair.")
        return
    a, b = _resolve(update, context, members, kind)
    if not a or not b:
        await update.effective_message.reply_text(f"☾ Use /{kind} with no arguments and let the Oracle choose — or reply to a member.")
        return
    pair = _ensure(_state(context.application).setdefault(_pair_key(chat.id, a["id"], b["id"]), {}))
    pair["uses"] += 1
    pair["last"] = int(datetime.now(timezone.utc).timestamp())
    deltas = {"bond": (4, 3, 5, 0, 4, 3, 1, -1), "thread": (2, 2, 3, 0, 3, 1, 0, -1), "orbit": (3, 1, 2, 0, 4, 3, 0, -1), "echo": (4, 2, 2, 0, 3, 2, 0, -1), "tether": (3, 4, 4, 0, 2, 2, 0, -2), "rift": (1, 0, 0, 5, 1, 1, 1, 3), "spark": (2, 1, 5, 0, 3, 4, 2, -1), "mirror": (3, 3, 3, 1, 2, 2, 0, 0), "crossing": (3, 2, 3, 0, 4, 3, 1, -1), "undertow": (2, 2, 5, 1, 3, 4, 1, -2), "verdict": (2, 2, 2, 0, 2, 2, 0, -1)}[kind]
    for field, delta in zip(("familiarity", "trust", "affinity", "tension", "momentum", "attention", "chaos", "distance"), deltas):
        pair[field] = max(0, min(100, pair[field] + delta))
    body = await _reading(kind, a, b, pair)
    await update.effective_message.reply_text(_reading_text(kind, a, b, body), disable_web_page_preview=True)


async def watch(update, context): await _watch_change(update, context, True)
async def unwatch(update, context): await _watch_change(update, context, False)
async def _watch_change(update, context, enabled):
    chat, _, members = await _targets(update); a, b = _resolve(update, context, members, "bond") if chat else (None, None)
    if not chat: return
    if not a or not b: await update.effective_message.reply_text("☾ Use /gaze with no arguments and let the Oracle choose — or reply to a member."); return
    p = _ensure(_state(context.application).setdefault(_pair_key(chat.id, a["id"], b["id"]), {})); p["watch"] = bool(enabled)
    if enabled: p["watch_since"] = int(datetime.now(timezone.utc).timestamp())
    await update.effective_message.reply_text(f"👁️ GAZE ESTABLISHED\n\n{_pair_display(a,b)}\n\nThe Oracle keeps this thread in its peripheral vision." if enabled else "☾ GAZE RELEASED\n\nThe Oracle has stepped away from this thread.")


def _cycle(now):
    local = now.astimezone(social_engine.ORACLE_TZ); boundary = local.replace(hour=ORACLE_HOUR, minute=ORACLE_MINUTE, second=0, microsecond=0); start = boundary - timedelta(days=1) if local < boundary else boundary; return start, start + timedelta(days=1)


async def sealed(update, context):
    chat, _, members = await _targets(update); a, b = _resolve(update, context, members, "bond") if chat else (None, None)
    if not chat: return
    if not a or not b: await update.effective_message.reply_text("☾ Use /veil with no arguments and let the Oracle choose — or reply to a member."); return
    now = datetime.now(timezone.utc); start, end = _cycle(now); key = _pair_key(chat.id, a["id"], b["id"]); lock_key = f"{key}:veil:{start.date().isoformat()}"; stored = await social_engine._get(lock_key)
    if not stored and now >= start.astimezone(timezone.utc): await social_engine._set(lock_key, str(int(end.timestamp())), ttl=172800); stored = str(int(end.timestamp()))
    until = int(stored) if stored else int(end.timestamp()); remaining = max(0, until - int(now.timestamp())); hours, rem = divmod(remaining, 3600); minutes, seconds = divmod(rem, 60)
    if not stored:
        text = f"🔒 THE VEIL IS SLEEPING\n\n{_pair_display(a,b)}\n\nThe next seal opens at exactly 00:07 IST.\n\n{hours:02d}h {minutes:02d}m {seconds:02d}s until the hour.\n\nThe Oracle does not move the hour."
    elif remaining <= 0: text = "☾ THE VEIL HAS OPENED.\n\nThe sealed hour has passed. The Oracle may reveal what was withheld."
    else: text = f"🔒 THE VEIL IS DRAWN\n\n{_pair_display(a,b)}\n\nThis reading is sealed until the next 00:07 IST.\n\n{hours:02d}h {minutes:02d}m {seconds:02d}s remaining\n\nThe lock cannot be moved, refreshed, or opened early.\n\n🌙 — Midnight Oracle"
    await update.effective_message.reply_text(text, disable_web_page_preview=True)


COMMANDS = {"bond":"bond","weave":"thread","orbit":"orbit","echo":"echo","anchor":"tether","fracture":"rift","ember":"spark","mirror":"mirror","crossing":"crossing","undertow":"undertow","edict":"verdict"}
ALIASES = {"thread":"thread","tether":"tether","rift":"rift","spark":"spark","verdict":"verdict"}


def register(app: Application):
    existing = {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}
    for command, kind in {**COMMANDS, **ALIASES}.items():
        if command in existing: continue
        async def handler(update, context, _kind=kind): await _ritual(_kind, update, context)
        app.add_handler(CommandHandler(command, handler), group=0)
    for command, callback in (("watch", watch), ("unwatch", unwatch), ("sealed", sealed), ("gaze", watch), ("release", unwatch), ("veil", sealed)):
        if command not in existing: app.add_handler(CommandHandler(command, callback), group=0)
    try:
        from .owner_oracle import register as register_owner; register_owner(app)
    except Exception:
        import logging; logging.getLogger("midnight.owner").exception("OWNER_SURFACE_REGISTRATION_FAILED")
