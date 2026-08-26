"""Stateful Midnight Cricket duel callbacks."""
from __future__ import annotations

import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes
from .storage import storage

SHOTS = {
    "cover": ("🏏", "Cover", 1, 0.72),
    "pull": ("🔥", "Pull", 2, 0.58),
    "loft": ("🚀", "Loft", 3, 0.43),
    "defend": ("🛡️", "Defend", 0, 0.88),
    "sweep": ("🌪️", "Sweep", 2, 0.62),
    "reverse": ("🌀", "Reverse", 4, 0.30),
}


def keyboard():
    buttons = [InlineKeyboardButton(f"{v[0]} {v[1]}", callback_data=f"mduel:{k}") for k, v in SHOTS.items()]
    return InlineKeyboardMarkup([buttons[:3], buttons[3:]])


def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{name}</a>'


def card(s: dict) -> str:
    return ("<b>🏏 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐃𝐔𝐄𝐋</b>\n\n"
            f"{mention(s['a'], s['a_name'])}  <b>{s['runs_a']}</b>  ×  <b>{s['runs_b']}</b>  {mention(s['b'], s['b_name'])}\n\n"
            f"Balls remaining: <b>{s['balls']}</b>\n"
            f"<i>{s['commentary']}</i>")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat.id
    s = await storage.load(f"cricket:duel:{chat_id}", None)
    if not isinstance(s, dict):
        await q.edit_message_text("🌘 This duel has already left the crease.")
        return
    uid = q.from_user.id
    if uid != s.get("turn"):
        await q.answer("It isn't your delivery yet.", show_alert=True)
        return
    shot = q.data.split(":", 1)[1]
    emoji, name, base, safety = SHOTS.get(shot, SHOTS["defend"])
    s["balls"] -= 1
    if random.random() > safety:
        runs = 0
        outcome = "WICKET"
    else:
        runs = base + random.choice([0, 0, 1])
        outcome = f"{runs} run{'s' if runs != 1 else ''}"
    if uid == s["a"]:
        s["runs_a"] += runs
        s["turn"] = s["b"]
        batter = s["a_name"]
    else:
        s["runs_b"] += runs
        s["turn"] = s["a"]
        batter = s["b_name"]
    s["commentary"] = f"{emoji} {batter} played the {name}. <b>{outcome}.</b>"
    finished = s["balls"] <= 0
    if finished:
        if s["runs_a"] > s["runs_b"]:
            result = f"🏆 {s['a_name']} owns the night by {s['runs_a'] - s['runs_b']} run(s)."
        elif s["runs_b"] > s["runs_a"]:
            result = f"🏆 {s['b_name']} owns the night by {s['runs_b'] - s['runs_a']} run(s)."
        else:
            result = "🌙 A draw. The Oracle refuses to pick a favourite."
        s["commentary"] = result
    await storage.set(f"cricket:duel:{chat_id}", s, ttl=1800)
    await q.edit_message_text(card(s), parse_mode=ParseMode.HTML, reply_markup=None if finished else keyboard())


def install(application) -> None:
    application.add_handler(CallbackQueryHandler(callback, pattern=r"^mduel:"), group=19)
