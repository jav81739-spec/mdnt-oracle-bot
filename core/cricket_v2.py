"""Midnight Cricket V2: a fast, skill-first mini game with no economy."""
from __future__ import annotations

import random
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from .storage import storage

SHOTS = {
    "defend": ("🛡️", "Defend", 0, 0.90),
    "cover": ("🏏", "Cover Drive", 1, 0.72),
    "sweep": ("🌪️", "Sweep", 2, 0.62),
    "pull": ("🔥", "Pull Shot", 2, 0.58),
    "loft": ("🚀", "Loft", 3, 0.43),
    "reverse": ("🌀", "Reverse", 4, 0.30),
}


def _keyboard(game: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(f"{e} {n}", callback_data=f"mc2:{game}:{k}") for k, (e, n, *_rest) in SHOTS.items()]
    return InlineKeyboardMarkup([buttons[:3], buttons[3:]])


def _card(s: dict[str, Any], title: str = "𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓") -> str:
    return (
        f"<b>🏏 {title}</b>\n\n"
        f"Score: <b>{s.get('runs', 0)}/{s.get('wickets', 0)}</b>  ·  Ball <b>{s.get('ball', 0)}/6</b>\n"
        f"Target: <b>{s.get('target', '—')}</b>\n\n"
        f"<i>{s.get('commentary', 'Choose your shot.')}</i>\n\n"
        "<code>☾ skill game · no economy rewards</code>"
    )


async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, cid = update.effective_user.id, update.effective_chat.id
    state = {"mode": "solo", "uid": uid, "runs": 0, "wickets": 0, "ball": 0, "target": random.choice([18, 22, 26, 30]), "commentary": "The crease is yours. Read the risk."}
    await storage.set(f"mc2:solo:{cid}:{uid}", state, ttl=1800)
    await update.effective_message.reply_text(_card(state), parse_mode=ParseMode.HTML, reply_markup=_keyboard("solo"))


async def cricketduel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.effective_message.reply_to_message
    if not reply or not reply.from_user or reply.from_user.is_bot:
        await update.effective_message.reply_text("🏏 Reply to a member with /cricketduel — Midnight will create the match automatically.")
        return
    a, b, cid = update.effective_user, reply.from_user, update.effective_chat.id
    if a.id == b.id:
        await update.effective_message.reply_text("🌘 You cannot challenge your own shadow.")
        return
    state = {"mode": "duel", "a": a.id, "b": b.id, "turn": a.id, "runs_a": 0, "runs_b": 0, "balls_a": 0, "balls_b": 0, "wickets_a": 0, "wickets_b": 0, "innings": 1, "commentary": f"{a.first_name} bats first. Six balls. Then the chase."}
    await storage.set(f"mc2:duel:{cid}", state, ttl=1800)
    await update.effective_message.reply_text(
        f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐃𝐔𝐄𝐋</b>\n\n{a.first_name} 🆚 {b.first_name}\n\n<i>Pure skill. No coins. No farming. Just six balls each.</i>\n\n{a.first_name} gets first bat.",
        parse_mode=ParseMode.HTML,
        reply_markup=_keyboard("duel"),
    )


async def _solo(q, chat_id: int, uid: int, shot: str) -> None:
    state = await storage.load(f"mc2:solo:{chat_id}:{uid}", None)
    if not isinstance(state, dict):
        await q.edit_message_text("🌘 That crease has expired. Start /cricket again.")
        return
    if state["ball"] >= 6 or state["wickets"] >= 2 or state["runs"] >= state["target"]:
        await q.edit_message_text(_card(state), parse_mode=ParseMode.HTML); return
    emoji, name, base, risk = SHOTS[shot]
    state["ball"] += 1
    if random.random() > risk:
        state["wickets"] += 1
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b> Midnight read the risk correctly."
    else:
        runs = base + random.choice([0, 0, 1])
        state["runs"] += runs
        state["commentary"] = f"{emoji} {name} — <b>{runs}</b> run{'s' if runs != 1 else ''}. {random.choice(['clean timing.', 'beautifully picked.', 'the crowd wakes up.', 'cold-blooded shot.'])}"
    if state["runs"] >= state["target"]:
        state["commentary"] = "🏆 <b>TARGET CHASED.</b> You owned the night."
    elif state["ball"] >= 6 or state["wickets"] >= 2:
        state["commentary"] += "\n\n🌙 <b>Innings over.</b>"
    await storage.set(f"mc2:solo:{chat_id}:{uid}", state, ttl=1800)
    active = state["ball"] < 6 and state["wickets"] < 2 and state["runs"] < state["target"]
    await q.edit_message_text(_card(state), parse_mode=ParseMode.HTML, reply_markup=_keyboard("solo") if active else None)


async def _duel(q, chat_id: int, uid: int, shot: str) -> None:
    key = f"mc2:duel:{chat_id}"
    state = await storage.load(key, None)
    if not isinstance(state, dict):
        await q.edit_message_text("🌘 That duel has expired. Start another /cricketduel."); return
    if uid != state.get("turn"):
        await q.answer("Not your ball 😭", show_alert=True); return
    emoji, name, base, risk = SHOTS[shot]
    batter = "a" if uid == state["a"] else "b"
    balls_key, runs_key, wickets_key = f"balls_{batter}", f"runs_{batter}", f"wickets_{batter}"
    state[balls_key] += 1
    if random.random() > risk:
        state[wickets_key] += 1; runs = 0
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b>"
    else:
        runs = base + random.choice([0, 0, 1]); state[runs_key] += runs
        state["commentary"] = f"{emoji} {name} — <b>{runs}</b> run{'s' if runs != 1 else ''}."
    if state[balls_key] >= 6:
        if state["innings"] == 1:
            state["innings"] = 2
            state["turn"] = state["b"]
            state["commentary"] = f"☀️ First innings done: <b>{state['runs_a']}/{state['wickets_a']}</b>. {state['b']} starts the chase."
        else:
            state["turn"] = None
    else:
        state["turn"] = state["b"] if uid == state["a"] else state["a"]
    if state["turn"] is None:
        if state["runs_a"] > state["runs_b"]: winner = state["a"]
        elif state["runs_b"] > state["runs_a"]: winner = state["b"]
        else: winner = 0
        names = {state["a"]: "𝐁𝐀𝐓𝐓𝐄𝐑 𝐀", state["b"]: "𝐁𝐀𝐓𝐓𝐄𝐑 𝐁"}
        state["commentary"] = "🏆 <b>DRAW.</b> Both sides finish level." if winner == 0 else f"🏆 <b>{names[winner]} WINS.</b> The crease has spoken."
    await storage.set(key, state, ttl=1800)
    label = f"{state['runs_a']}/{state['wickets_a']}  🆚  {state['runs_b']}/{state['wickets_b']}"
    text = f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐃𝐔𝐄𝐋</b>\n\n{label}\n\n<i>{state['commentary']}</i>"
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=_keyboard("duel") if state["turn"] else None)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    _, game, shot = q.data.split(":", 2)
    if shot not in SHOTS: return
    if game == "solo": await _solo(q, q.message.chat.id, q.from_user.id, shot)
    else: await _duel(q, q.message.chat.id, q.from_user.id, shot)


def install(application) -> None:
    application.add_handler(CommandHandler(["cricket", "cricketgame"], cricket), group=16)
    application.add_handler(CommandHandler(["cricketduel", "cricketvs"], cricketduel), group=16)
    application.add_handler(CallbackQueryHandler(callback, pattern=r"^mc2:"), group=16)
