"""Unique Midnight V2 features retained during final-integration merge.

This module intentionally contains only capabilities not already owned by the
final integration surface: V2 identity/world events, bond/oracle pairing,
Midnight Vow, social-signal reading, and skill-first cricket.
"""
from __future__ import annotations

import hashlib
import html
import random
from datetime import datetime, timezone
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, ContextTypes

from .storage import storage


def _mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(name or "Midnight Soul")}</a>'


def _target(update: Update):
    message = update.effective_message
    reply = message.reply_to_message if message else None
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return None


# ---------------------------------------------------------------------------
# Identity / world layer from V2. Kept separate from the existing aesthetic
# identity command because these are persistent progression/world mechanics.
# ---------------------------------------------------------------------------
ARCHETYPES = (
    ("☾", "Nightwalker"), ("✦", "Oracle's Favourite"), ("⚡", "Chaos Spark"),
    ("𖤓", "Moonstruck"), ("◈", "Shadow Strategist"), ("♟", "Quiet Force"),
)
TITLES = ("Midnight Soul", "Afterdark Ace", "Moonlit Menace", "Silent Legend", "Night Shift", "Oracle-Touched")
ACHIEVEMENTS = {
    "first": ("✦", "First Light", "You entered the Midnight world."),
    "social": ("☾", "Social Gravity", "You became part of the room's rhythm."),
    "survivor": ("𖤓", "Still Awake", "You kept the night alive."),
}
WORLD_EVENTS = (
    ("🌑", "THE ECLIPSE", "For the next few moments, the Oracle may choose anyone in the room."),
    ("☄️", "THE COMET", "One unexpected member becomes tonight's catalyst. Watch what follows."),
    ("𖤓", "THE HIDDEN HOUR", "A rare event has opened. No one gets to know the rules in advance."),
    ("⚡", "RED MOON", "The room has become unstable. Two names will be drawn when the next trigger lands."),
)


async def _profile(chat_id: int, uid: int) -> dict[str, Any]:
    key = f"identity:{chat_id}:{uid}"
    value = await storage.load(key, None)
    if isinstance(value, dict):
        return value
    icon, archetype = random.choice(ARCHETYPES)
    value = {"xp": 0, "level": 1, "title": random.choice(TITLES), "icon": icon,
             "archetype": archetype, "luck": random.randint(42, 78),
             "chaos": random.randint(18, 64), "achievements": ["first"]}
    await storage.set(key, value, ttl=0)
    return value


async def _gain(chat_id: int, uid: int, amount: int = 5) -> dict[str, Any]:
    profile = await _profile(chat_id, uid)
    profile["xp"] = int(profile.get("xp", 0)) + amount
    profile["level"] = 1 + profile["xp"] // 100
    achievements = list(profile.get("achievements", []))
    if profile["level"] >= 3 and "social" not in achievements:
        achievements.append("social")
    profile["achievements"] = achievements
    await storage.set(f"identity:{chat_id}:{uid}", profile, ttl=0)
    return profile


async def mprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, chat = update.effective_user, update.effective_chat
    profile = await _gain(chat.id, user.id)
    marks = []
    for key in profile.get("achievements", []):
        icon, name, _ = ACHIEVEMENTS.get(key, ("✦", key, ""))
        marks.append(f"{icon} {name}")
    await update.effective_message.reply_text(
        f"<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐈𝐃𝐄𝐍𝐓𝐈𝐓𝐘</b>\n\n"
        f"{profile['icon']} <b>{html.escape(str(profile['title']))}</b>\n"
        f"<i>{html.escape(str(profile['archetype']))}</i>\n\n"
        f"<b>LEVEL</b> {profile['level']} · <b>XP</b> {profile['xp']}\n"
        f"<b>LUCK</b> {profile['luck']}% · <b>CHAOS</b> {profile['chaos']}%\n\n"
        f"<b>𝐌𝐀𝐑𝐊𝐒</b>\n{' · '.join(marks) if marks else 'None yet.'}\n\n"
        "<i>Your identity changes through what you actually do in Midnight.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await _profile(update.effective_chat.id, update.effective_user.id)
    lines = []
    for key, (icon, name, description) in ACHIEVEMENTS.items():
        mark = "✓" if key in profile.get("achievements", []) else "·"
        lines.append(f"{mark} {icon} <b>{name}</b> — {description}")
    await update.effective_message.reply_text(
        "<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐌𝐀𝐑𝐊𝐒</b>\n\n" + "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


async def midnightevent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    icon, title, text = random.choice(WORLD_EVENTS)
    await update.effective_message.reply_text(
        f"<b>{icon} 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐖𝐎𝐑𝐋𝐃 𝐄𝐕𝐄𝐍𝐓 · {title}</b>\n\n"
        f"<i>{text}</i>\n\n<b>STATE:</b> <i>awake</i>\n\n"
        "<i>Some nights are ordinary. This one isn't.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# V2 bond / pairing / vow. These are command-driven and never call the
# autonomous scheduler.
# ---------------------------------------------------------------------------
BOND_LINES = (
    ("✦ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐁𝐎𝐍𝐃 ✦", "Two paths crossed under the same night."),
    ("☾ 𝐐𝐔𝐈𝐄𝐓 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 ☽", "Interesting chemistry. Midnight is only measuring the vibe."),
    ("𖤓 𝐍𝐈𝐆𝐇𝐓 𝐏𝐀𝐈𝐑𝐈𝐍𝐆 𖤓", "No nominations. The Oracle picked this one."),
)


def _recent_members(chat_id: int) -> list[dict[str, Any]]:
    # Kept synchronous at the call site only as a placeholder; actual command
    # handlers below use the current reply target when available.
    return []


async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("☾ Reply to someone's message with /bond and let Midnight test the pairing.")
        return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 The Oracle refuses to pair you with your own reflection.")
        return
    title, line = random.choice(BOND_LINES)
    score = random.randint(41, 99)
    await update.effective_message.reply_text(
        f"<b>{title}</b>\n\n{_mention(actor.id, actor.first_name)} × {_mention(target.id, target.first_name)}\n\n"
        f"<i>{line}</i>\n\n<b>𝐍𝐈𝐆𝐇𝐓 𝐒𝐘𝐍𝐂</b> · <b>{score}%</b>\n\n"
        "<i>For fun only. The score says nothing about real feelings.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


async def oraclepair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("☾ Reply to a member with /oraclepair and let the Oracle choose the night pairing.")
        return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 The Oracle needs two different souls.")
        return
    score = random.randint(41, 99)
    await update.effective_message.reply_text(
        "<b>✦ 𝐓𝐇𝐄 𝐎𝐑𝐀𝐂𝐋𝐄 𝐂𝐇𝐎𝐎𝐒𝐄𝐒 ✦</b>\n\n"
        f"{_mention(actor.id, actor.first_name)} × {_mention(target.id, target.first_name)}\n\n"
        f"<b>{score}% 𝐍𝐈𝐆𝐇𝐓 𝐒𝐘𝐍𝐂</b>\n\n"
        "<i>No nominations. No applications. Just tonight's fictional pairing.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


async def vow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("☾ Reply to a member to open a Midnight Vow.")
        return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 A vow needs two people, not a reflection.")
        return
    rule = random.choice(("No disappearing mid-conversation.", "One honest answer each.", "Choose the song for the other.", "Make each other laugh once."))
    await update.effective_message.reply_text(
        "<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐕𝐎𝐖 𖤓</b>\n\n"
        f"{_mention(actor.id, actor.first_name)} × {_mention(target.id, target.first_name)}\n\n"
        f"<i>Tonight's rule:</i> <b>{html.escape(rule)}</b>\n\n"
        "<i>Purely a group-game ritual.</i> ✦",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Social signal reader: no hidden-fact claims.
# ---------------------------------------------------------------------------
def _signal_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        choices = (
            "🟣 <b>VIBE SIGNAL</b>\n\nMidnight picked up a social moment in the room.",
            "🔵 <b>MOMENT SIGNAL</b>\n\nSomething in the room feels worth noticing.",
            "🌙 <b>NIGHT SIGNAL</b>\n\nStay curious, but don't mistake a vibe for proof.",
        )
        reason = random.choice(choices)
        return "☾ <b>SIGNAL CHECK</b>\n\n" + reason + "\n\n<i>Midnight chose this signal automatically. It does not claim hidden facts.</i> 🌙"
    lower = text.lower()
    markers = []
    if any(x in lower for x in ("official", "confirmed", "announcement", "statement", "source", "reported")):
        markers.append("the wording claims external confirmation")
    if "?" in text:
        markers.append("the message contains an open question")
    if any(x in lower for x in ("i think", "maybe", "probably", "feels like", "lagta hai", "shayad", "mujhe lagta")):
        markers.append("the wording signals interpretation rather than verification")
    if any(x in lower for x in ("always", "never", "everyone", "nobody", "definitely", "100%")):
        markers.append("absolute wording may overstate certainty")
    status = "🟡 <b>MIXED SIGNAL</b>" if markers else "🟢 <b>CLEAR SIGNAL</b>"
    reason = "; ".join(markers[:2]) + "." if markers else "Nothing in the wording alone establishes a hidden fact."
    return f"☾ <b>SIGNAL CHECK</b>\n\n{status}\n\n<i>{html.escape(reason)}</i>\n\n<b>Rule:</b> facts first, interpretation second. 🌙"


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = " ".join(context.args or []).strip()
    if not text and message and message.reply_to_message:
        replied = message.reply_to_message
        text = replied.text or replied.caption or ""
    await message.reply_text(_signal_text(text), parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Skill-first cricket from V2, using the final branch's durable storage.
# ---------------------------------------------------------------------------
SHOTS = {
    "defend": ("🛡️", "Defend", (0, 1), 0.94),
    "cover": ("🏏", "Cover Drive", (1, 2, 4), 0.78),
    "cut": ("⚡", "Square Cut", (1, 2, 4), 0.73),
    "sweep": ("🌪️", "Sweep", (1, 2, 4), 0.67),
    "pull": ("🔥", "Pull Shot", (2, 4, 6), 0.61),
    "hook": ("💥", "Hook Shot", (2, 4, 6), 0.56),
    "loft": ("🚀", "Lofted Drive", (4, 6), 0.45),
    "straight": ("🎯", "Straight Drive", (2, 4, 6), 0.69),
    "helicopter": ("🚁", "Helicopter Shot", (4, 6), 0.42),
    "reverse": ("🌀", "Reverse Sweep", (1, 4, 6), 0.38),
}


def _cricket_keyboard(game: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(f"{emoji} {name}", callback_data=f"mc2:{game}:{key}") for key, (emoji, name, *_rest) in SHOTS.items()]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def _card(state: dict[str, Any]) -> str:
    return (
        "<b>🏏 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\n"
        f"Score: <b>{state.get('runs', 0)}/{state.get('wickets', 0)}</b> · Ball <b>{state.get('ball', 0)}/6</b>\n"
        f"Target: <b>{state.get('target', '—')}</b>\n\n"
        f"<i>{state.get('commentary', 'Choose your shot.')}</i>\n\n"
        "<code>☾ skill game · no economy rewards</code>"
    )


async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, chat_id = update.effective_user.id, update.effective_chat.id
    state = {"uid": uid, "runs": 0, "wickets": 0, "ball": 0, "target": random.choice((18, 22, 26, 30)), "commentary": "The crease is yours. Pick your shot."}
    await storage.set(f"mc2:solo:{chat_id}:{uid}", state, ttl=1800)
    await update.effective_message.reply_text(_card(state), parse_mode=ParseMode.HTML, reply_markup=_cricket_keyboard("solo"))


async def cricketduel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("🏏 Reply to a member with /cricketduel to create the match.")
        return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 You cannot challenge your own shadow.")
        return
    state = {"a": actor.id, "b": target.id, "turn": actor.id, "runs_a": 0, "runs_b": 0,
             "balls_a": 0, "balls_b": 0, "wickets_a": 0, "wickets_b": 0, "innings": 1,
             "commentary": f"{actor.first_name} bats first. Six balls. Then the chase."}
    await storage.set(f"mc2:duel:{update.effective_chat.id}", state, ttl=1800)
    await update.effective_message.reply_text(
        f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐃𝐔𝐄𝐋</b>\n\n"
        f"{html.escape(actor.first_name)} 🆚 {html.escape(target.first_name)}\n\n"
        "<i>Pure skill. Six balls each. No coins. No farming.</i>",
        parse_mode=ParseMode.HTML, reply_markup=_cricket_keyboard("duel"),
    )


async def _solo(q, chat_id: int, uid: int, shot: str) -> None:
    key = f"mc2:solo:{chat_id}:{uid}"
    state = await storage.load(key, None)
    if not isinstance(state, dict):
        await q.edit_message_text("🌘 That crease has expired. Start /cricket again.")
        return
    if state.get("ball", 0) >= 6 or state.get("wickets", 0) >= 2 or state.get("runs", 0) >= state.get("target", 999):
        await q.edit_message_text(_card(state), parse_mode=ParseMode.HTML)
        return
    emoji, name, outcomes, risk = SHOTS[shot]
    state["ball"] += 1
    if random.random() > risk:
        state["wickets"] += 1
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b> Risk did not pay."
    else:
        result = random.choice(outcomes)
        state["runs"] += result
        state["commentary"] = f"{emoji} {name} — <b>{result}</b> run{'s' if result != 1 else ''}."
    finished = state["runs"] >= state["target"] or state["ball"] >= 6 or state["wickets"] >= 2
    if state["runs"] >= state["target"]:
        state["commentary"] = "🏆 <b>TARGET CHASED.</b> You owned the night."
    await storage.set(key, state, ttl=1800)
    await q.edit_message_text(_card(state), parse_mode=ParseMode.HTML, reply_markup=_cricket_keyboard("solo") if not finished else None)


async def _duel(q, chat_id: int, uid: int, shot: str) -> None:
    key = f"mc2:duel:{chat_id}"
    state = await storage.load(key, None)
    if not isinstance(state, dict):
        await q.edit_message_text("🌘 That duel has expired. Start another /cricketduel.")
        return
    if state.get("turn") != uid:
        await q.answer("Not your ball 😭", show_alert=True)
        return
    batter = "a" if state["turn"] == state["a"] else "b"
    emoji, name, outcomes, risk = SHOTS[shot]
    balls_key, runs_key, wickets_key = f"balls_{batter}", f"runs_{batter}", f"wickets_{batter}"
    state[balls_key] += 1
    if random.random() > risk:
        state[wickets_key] += 1
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b>"
    else:
        result = random.choice(outcomes)
        state[runs_key] += result
        state["commentary"] = f"{emoji} {name} — <b>{result}</b> run{'s' if result != 1 else ''}."
    innings_over = state[balls_key] >= 6 or state[wickets_key] >= 2
    if state["innings"] == 1 and innings_over:
        state["innings"] = 2; state["turn"] = state["b"]
    elif state["innings"] == 2:
        target = state["runs_a"]
        if state["runs_b"] >= target or innings_over: state["turn"] = None
    await storage.set(key, state, ttl=1800)
    if state["turn"] is None:
        if state["runs_b"] > state["runs_a"]: state["commentary"] = "🏆 <b>BATTER B WINS.</b>"
        elif state["runs_a"] > state["runs_b"]: state["commentary"] = "🏆 <b>BATTER A WINS.</b>"
        else: state["commentary"] = "🏆 <b>DRAW.</b> Both sides finish level."
    text = f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐃𝐔𝐄𝐋</b>\n\n{state['runs_a']}/{state['wickets_a']} 🆚 {state['runs_b']}/{state['wickets_b']}\n\n<i>{state['commentary']}</i>"
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=_cricket_keyboard("duel") if state["turn"] else None)


async def cricket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return
    await query.answer()
    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[2] not in SHOTS or parts[1] not in {"solo", "duel"}:
        return
    if parts[1] == "solo":
        await _solo(query, query.message.chat.id, query.from_user.id, parts[2])
    else:
        await _duel(query, query.message.chat.id, query.from_user.id, parts[2])


def _existing(app) -> set[str]:
    return {str(command).lower().lstrip("/") for group in getattr(app, "handlers", {}).values() for handler in group for command in (getattr(handler, "commands", None) or ())}


def register(app) -> None:
    existing = _existing(app)
    additions = (
        ("bond", bond), ("oraclepair", oraclepair), ("vow", vow),
        ("mprofile", mprofile), ("achievements", achievements), ("midnightevent", midnightevent),
        ("signal", signal), ("signalcheck", signal),
        ("cricket", cricket), ("cricketduel", cricketduel),
    )
    for command, callback in additions:
        if command not in existing:
            app.add_handler(CommandHandler(command, callback), group=16)
            existing.add(command)
    if not any(getattr(handler, "callback", None) is cricket_callback for group in getattr(app, "handlers", {}).values() for handler in group):
        app.add_handler(CallbackQueryHandler(cricket_callback, pattern=r"^mc2:"), group=16)
