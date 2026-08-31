"""Deduplicated V2 extras for the final integration runtime.

Only commands with no existing owner are registered here. Existing legacy,
relationship, scheduler, and Help surfaces remain authoritative.
"""
from __future__ import annotations

import html
import random
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from .storage import storage


def _mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(name or "Midnight Soul")}</a>'


def _target(update):
    message = update.effective_message
    reply = message.reply_to_message if message else None
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return None


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


async def mprofile(update, context) -> None:
    user, chat = update.effective_user, update.effective_chat
    profile = await _profile(chat.id, user.id)
    profile["xp"] = int(profile.get("xp", 0)) + 5
    profile["level"] = 1 + profile["xp"] // 100
    if profile["level"] >= 3 and "social" not in profile.setdefault("achievements", []):
        profile["achievements"].append("social")
    await storage.set(f"identity:{chat.id}:{user.id}", profile, ttl=0)
    marks = []
    for key in profile.get("achievements", []):
        icon, name, _ = ACHIEVEMENTS.get(key, ("✦", key, "")); marks.append(f"{icon} {name}")
    await update.effective_message.reply_text(
        f"<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐈𝐃𝐄𝐍𝐓𝐈𝐓𝐘</b>\n\n"
        f"{profile['icon']} <b>{html.escape(str(profile['title']))}</b>\n<i>{html.escape(str(profile['archetype']))}</i>\n\n"
        f"<b>LEVEL</b> {profile['level']} · <b>XP</b> {profile['xp']}\n"
        f"<b>LUCK</b> {profile['luck']}% · <b>CHAOS</b> {profile['chaos']}%\n\n"
        f"<b>𝐌𝐀𝐑𝐊𝐒</b>\n{' · '.join(marks)}\n\n"
        "<i>Your identity changes through what you actually do in Midnight.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


async def achievements(update, context) -> None:
    profile = await _profile(update.effective_chat.id, update.effective_user.id)
    lines = []
    for key, (icon, name, description) in ACHIEVEMENTS.items():
        mark = "✓" if key in profile.get("achievements", []) else "·"
        lines.append(f"{mark} {icon} <b>{name}</b> — {description}")
    await update.effective_message.reply_text("<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐌𝐀𝐑𝐊𝐒</b>\n\n" + "\n".join(lines), parse_mode=ParseMode.HTML)


async def midnightevent(update, context) -> None:
    icon, title, text = random.choice(WORLD_EVENTS)
    await update.effective_message.reply_text(
        f"<b>{icon} 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐖𝐎𝐑𝐋𝐃 𝐄𝐕𝐄𝐍𝐓 · {title}</b>\n\n"
        f"<i>{text}</i>\n\n<b>STATE:</b> <i>awake</i>\n\n"
        "<i>Some nights are ordinary. This one isn't.</i> 🌙", parse_mode=ParseMode.HTML)


async def oraclepair(update, context) -> None:
    target = _target(update); actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("☾ Reply to a member with /oraclepair and let the Oracle choose the pairing."); return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 The Oracle needs two different souls."); return
    score = random.randint(41, 99)
    await update.effective_message.reply_text(
        "<b>✦ 𝐓𝐇𝐄 𝐎𝐑𝐀𝐂𝐋𝐄 𝐂𝐇𝐎𝐎𝐒𝐄𝐒 ✦</b>\n\n"
        f"{_mention(actor.id, actor.first_name)} × {_mention(target.id, target.first_name)}\n\n"
        f"<b>{score}% 𝐍𝐈𝐆𝐇𝐓 𝐒𝐘𝐍𝐂</b>\n\n<i>No nominations. No applications. Just tonight's fictional pairing.</i> 🌙",
        parse_mode=ParseMode.HTML)


async def vow(update, context) -> None:
    target = _target(update); actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("☾ Reply to a member to open a Midnight Vow."); return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 A vow needs two people, not a reflection."); return
    rule = random.choice(("No disappearing mid-conversation.", "One honest answer each.", "Choose the song for the other.", "Make each other laugh once."))
    await update.effective_message.reply_text(
        "<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐕𝐎𝐖 𖤓</b>\n\n"
        f"{_mention(actor.id, actor.first_name)} × {_mention(target.id, target.first_name)}\n\n"
        f"<i>Tonight's rule:</i> <b>{html.escape(rule)}</b>\n\n<i>Purely a group-game ritual.</i> ✦",
        parse_mode=ParseMode.HTML)


SHOTS = {
    "defend": ("🛡️", "Defend", (0, 1), 0.94), "cover": ("🏏", "Cover Drive", (1, 2, 4), 0.78),
    "cut": ("⚡", "Square Cut", (1, 2, 4), 0.73), "sweep": ("🌪️", "Sweep", (1, 2, 4), 0.67),
    "pull": ("🔥", "Pull Shot", (2, 4, 6), 0.61), "hook": ("💥", "Hook Shot", (2, 4, 6), 0.56),
    "loft": ("🚀", "Lofted Drive", (4, 6), 0.45), "straight": ("🎯", "Straight Drive", (2, 4, 6), 0.69),
    "helicopter": ("🚁", "Helicopter Shot", (4, 6), 0.42), "reverse": ("🌀", "Reverse Sweep", (1, 4, 6), 0.38),
}


def _keyboard(game):
    buttons = [InlineKeyboardButton(f"{e} {n}", callback_data=f"v2cricket:{game}:{k}") for k, (e, n, *_r) in SHOTS.items()]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def _card(state):
    return f"<b>🏏 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\nScore: <b>{state['runs']}/{state['wickets']}</b> · Ball <b>{state['ball']}/6</b>\nTarget: <b>{state['target']}</b>\n\n<i>{state['commentary']}</i>\n\n<code>☾ skill game · no economy rewards</code>"


async def cricketduel(update, context) -> None:
    target = _target(update); actor = update.effective_user
    if not target:
        await update.effective_message.reply_text("🏏 Reply to a member with /cricketduel to create the match."); return
    if target.id == actor.id:
        await update.effective_message.reply_text("🌘 You cannot challenge your own shadow."); return
    state = {"a": actor.id, "b": target.id, "turn": actor.id, "runs_a": 0, "runs_b": 0,
             "balls_a": 0, "balls_b": 0, "wickets_a": 0, "wickets_b": 0, "innings": 1,
             "commentary": f"{actor.first_name} bats first. Six balls. Then the chase."}
    await storage.set(f"v2cricket:duel:{update.effective_chat.id}", state, ttl=1800)
    await update.effective_message.reply_text(
        f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐃𝐔𝐄𝐋</b>\n\n{html.escape(actor.first_name)} 🆚 {html.escape(target.first_name)}\n\n<i>Pure skill. Six balls each. No coins. No farming.</i>",
        parse_mode=ParseMode.HTML, reply_markup=_keyboard("duel"))


async def cricket_callback(update, context) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user: return
    await query.answer()
    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[0] != "v2cricket" or parts[2] not in SHOTS: return
    if parts[1] != "duel": return
    state = await storage.load(f"v2cricket:duel:{query.message.chat.id}", None)
    if not isinstance(state, dict):
        await query.edit_message_text("🌘 That duel has expired. Start another /cricketduel."); return
    if state.get("turn") != query.from_user.id:
        await query.answer("Not your ball 😭", show_alert=True); return
    batter = "a" if state["turn"] == state["a"] else "b"
    emoji, name, outcomes, risk = SHOTS[parts[2]]
    state[f"balls_{batter}"] += 1
    if random.random() > risk:
        state[f"wickets_{batter}"] += 1; state["commentary"] = f"{emoji} {name} — <b>WICKET.</b>"
    else:
        runs = random.choice(outcomes); state[f"runs_{batter}"] += runs
        state["commentary"] = f"{emoji} {name} — <b>{runs}</b> run{'s' if runs != 1 else ''}."
    if state["innings"] == 1 and (state["balls_a"] >= 6 or state["wickets_a"] >= 2):
        state["innings"] = 2; state["turn"] = state["b"]
    elif state["innings"] == 2:
        if state["runs_b"] >= state["runs_a"] or state["balls_b"] >= 6 or state["wickets_b"] >= 2:
            state["turn"] = None
    else:
        state["turn"] = state["a"]
    if state["turn"] is None:
        if state["runs_b"] > state["runs_a"]: state["commentary"] = "🏆 <b>BATTER B WINS.</b>"
        elif state["runs_a"] > state["runs_b"]: state["commentary"] = "🏆 <b>BATTER A WINS.</b>"
        else: state["commentary"] = "🏆 <b>DRAW.</b> Both sides finish level."
    await storage.set(f"v2cricket:duel:{query.message.chat.id}", state, ttl=1800)
    await query.edit_message_text(
        f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐃𝐔𝐄𝐋</b>\n\n{state['runs_a']}/{state['wickets_a']} 🆚 {state['runs_b']}/{state['wickets_b']}\n\n<i>{state['commentary']}</i>",
        parse_mode=ParseMode.HTML, reply_markup=_keyboard("duel") if state["turn"] else None)


def _existing(app):
    return {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}


def register(app):
    existing = _existing(app)
    # These are the only commands found in V2 history without an owner in
    # final-integration. Do not shadow the legacy bond/signal/cricket handlers.
    for command, callback in (
        ("oraclepair", oraclepair), ("vow", vow), ("mprofile", mprofile),
        ("achievements", achievements), ("midnightevent", midnightevent),
        ("cricketduel", cricketduel),
    ):
        if command not in existing:
            app.add_handler(CommandHandler(command, callback), group=16); existing.add(command)
    if not any(getattr(h, "callback", None) is cricket_callback for hs in getattr(app, "handlers", {}).values() for h in hs):
        app.add_handler(CallbackQueryHandler(cricket_callback, pattern=r"^v2cricket:"), group=16)
