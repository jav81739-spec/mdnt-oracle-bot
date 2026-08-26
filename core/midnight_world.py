"""Living Midnight Oracle systems: identity, progression and rare world events."""
from __future__ import annotations

import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from .storage import storage

ARCHETYPES = [
    ("☾", "Nightwalker"), ("✦", "Oracle's Favourite"), ("⚡", "Chaos Spark"),
    ("𖤓", "Moonstruck"), ("◈", "Shadow Strategist"), ("♟", "Quiet Force"),
]
TITLES = ["Midnight Soul", "Afterdark Ace", "Moonlit Menace", "Silent Legend", "Night Shift", "Oracle-Touched"]
ACHIEVEMENTS = {
    "first": ("✦", "First Light", "You entered the Midnight world."),
    "social": ("☾", "Social Gravity", "You became part of the room's rhythm."),
    "survivor": ("𖤓", "Still Awake", "You kept the night alive."),
}

async def _profile(chat_id: int, uid: int) -> dict:
    key = f"identity:{chat_id}:{uid}"
    value = await storage.load(key, None)
    if isinstance(value, dict):
        return value
    icon, archetype = random.choice(ARCHETYPES)
    value = {"xp": 0, "level": 1, "title": random.choice(TITLES), "icon": icon, "archetype": archetype, "luck": random.randint(42, 78), "chaos": random.randint(18, 64), "achievements": ["first"]}
    await storage.set(key, value, ttl=0)
    return value

async def _gain(chat_id: int, uid: int, amount: int = 7) -> dict:
    p = await _profile(chat_id, uid)
    p["xp"] = int(p.get("xp", 0)) + amount
    p["level"] = 1 + p["xp"] // 100
    if p["level"] >= 3 and "social" not in p["achievements"]:
        p["achievements"].append("social")
    await storage.set(f"identity:{chat_id}:{uid}", p, ttl=0)
    return p

async def midnight_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user; c = update.effective_chat
    p = await _gain(c.id, u.id, 5)
    medals = []
    for a in p.get("achievements", []):
        icon, name, _ = ACHIEVEMENTS.get(a, ("✦", a, "")); medals.append(f"{icon} {name}")
    await update.effective_message.reply_text(
        f"<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐈𝐃𝐄𝐍𝐓𝐈𝐓𝐘</b>\n\n"
        f"{p['icon']} <b>{p['title']}</b>\n<i>{p['archetype']}</i>\n\n"
        f"<b>LEVEL</b> {p['level']}  ·  <b>XP</b> {p['xp']}\n"
        f"<b>LUCK</b> {p['luck']}%  ·  <b>CHAOS</b> {p['chaos']}%\n\n"
        f"<b>𝐌𝐀𝐑𝐊𝐒</b>\n" + (" · ".join(medals) if medals else "None yet.") + "\n\n"
        "<i>Your identity changes through what you actually do in Midnight.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )

async def midnight_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    p = await _profile(update.effective_chat.id, update.effective_user.id)
    lines = []
    for key, (icon, name, desc) in ACHIEVEMENTS.items():
        mark = "✓" if key in p.get("achievements", []) else "·"
        lines.append(f"{mark} {icon} <b>{name}</b> — {desc}")
    await update.effective_message.reply_text("<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐌𝐀𝐑𝐊𝐒</b>\n\n" + "\n".join(lines), parse_mode=ParseMode.HTML)

WORLD_EVENTS = [
    ("🌑", "THE ECLIPSE", "For the next few moments, the Oracle may choose anyone in the room."),
    ("☄️", "THE COMET", "One unexpected member becomes tonight's catalyst. Watch what follows."),
    ("𖤓", "THE HIDDEN HOUR", "A rare event has opened. No one gets to know the rules in advance."),
    ("⚡", "RED MOON", "The room has become unstable. Two names will be drawn when the next trigger lands."),
]

async def midnight_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    icon, title, text = random.choice(WORLD_EVENTS)
    await update.effective_message.reply_text(
        f"<b>{icon} 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐖𝐎𝐑𝐋𝐃 𝐄𝐕𝐄𝐍𝐓 · {title}</b>\n\n"
        f"<i>{text}</i>\n\n<b>STATE:</b> <i>awake</i>\n\n"
        "<i>Some nights are ordinary. This one isn't.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )

async def world_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query; await q.answer()
    await q.edit_message_reply_markup(reply_markup=None)


def install(application) -> None:
    application.add_handler(CommandHandler(["midnightprofile", "mprofile", "identity"], midnight_profile), group=21)
    application.add_handler(CommandHandler(["achievements", "marks"], midnight_achievements), group=21)
    application.add_handler(CommandHandler(["midnightevent", "worldevent"], midnight_event), group=21)
    application.add_handler(CallbackQueryHandler(world_callback, pattern=r"^mworld:"), group=21)
