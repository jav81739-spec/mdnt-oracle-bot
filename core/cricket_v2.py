"""Midnight Cricket V2: skill-first cricket with optional GIPHY replays."""
from __future__ import annotations

import html
import random
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from .storage import storage
from handlers.chat import get_gif_url

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

GIF_QUERIES = {
    6: ("professional cricket six sixes batsman", "🔥 SIX! Professional cricket replay"),
    4: ("professional cricket four boundary batsman", "🏏 FOUR! Professional cricket replay"),
    "wicket": ("professional cricket wicket celebration", "💥 WICKET! Professional cricket replay"),
    "win": ("professional cricket winning celebration", "🏆 Match-winning cricket replay"),
}


def _keyboard(game: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(f"{e} {n}", callback_data=f"mc2:{game}:{k}") for k, (e, n, *_rest) in SHOTS.items()]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def _card(s: dict[str, Any], title: str = "𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓") -> str:
    return (
        f"<b>🏏 {title}</b>\n\n"
        f"Score: <b>{s.get('runs', 0)}/{s.get('wickets', 0)}</b>  ·  Ball <b>{s.get('ball', 0)}/6</b>\n"
        f"Target: <b>{s.get('target', '—')}</b>\n\n"
        f"<i>{s.get('commentary', 'Choose your shot.')}</i>\n\n"
        "<code>☾ skill game · visual replays · no economy rewards</code>"
    )


async def _preview(bot, chat_id: int, result: int | str, caption: str = "") -> None:
    """Use the configured GIPHY API for cricket footage; visuals never break gameplay."""
    query_info = GIF_QUERIES.get(result)
    if not query_info:
        return
    query, fallback_caption = query_info
    try:
        gif_url = await get_gif_url(query)
        if gif_url:
            await bot.send_animation(chat_id=chat_id, animation=gif_url, caption=caption or fallback_caption, parse_mode=ParseMode.HTML)
            return
    except Exception:
        # GIPHY is an enhancement. Never turn a GIF failure into a game failure.
        pass


async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, cid = update.effective_user.id, update.effective_chat.id
    state = {
        "mode": "solo", "uid": uid, "runs": 0, "wickets": 0, "ball": 0,
        "target": random.choice([18, 22, 26, 30]),
        "commentary": "The crease is yours. Pick your shot.",
    }
    await storage.set(f"mc2:solo:{cid}:{uid}", state, ttl=1800)
    await update.effective_message.reply_text(
        "🏏 <b>Midnight Cricket</b>\n\nSix balls. One target. Make your shots count. 🌙",
        parse_mode=ParseMode.HTML,
    )
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
    state = {
        "mode": "duel", "a": a.id, "b": b.id, "turn": a.id,
        "runs_a": 0, "runs_b": 0, "balls_a": 0, "balls_b": 0,
        "wickets_a": 0, "wickets_b": 0, "innings": 1,
        "commentary": f"{a.first_name} bats first. Six balls. Then the chase.",
    }
    await storage.set(f"mc2:duel:{cid}", state, ttl=1800)
    await update.effective_message.reply_text(
        f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐃𝐔𝐄𝐋</b>\n\n"
        f"{html.escape(a.first_name)} 🆚 {html.escape(b.first_name)}\n\n"
        "<i>Pure skill. Six balls each. No coins. No farming.</i>\n\n"
        f"{html.escape(a.first_name)} bats first.",
        parse_mode=ParseMode.HTML,
        reply_markup=_keyboard("duel"),
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
        result: int | str = "wicket"
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b> Risk did not pay."
    else:
        result = random.choice(outcomes)
        state["runs"] += result
        state["commentary"] = f"{emoji} {name} — <b>{result}</b> run{'s' if result != 1 else ''}. {random.choice(['clean timing.', 'beautifully picked.', 'the crowd wakes up.', 'cold-blooded shot.'])}"
    finished = state["runs"] >= state["target"] or state["ball"] >= 6 or state["wickets"] >= 2
    if state["runs"] >= state["target"]:
        state["commentary"] = "🏆 <b>TARGET CHASED.</b> You owned the night."
    elif state["ball"] >= 6 or state["wickets"] >= 2:
        state["commentary"] += "\n\n🌙 <b>Innings over.</b>"
    await storage.set(key, state, ttl=1800)
    await q.edit_message_text(_card(state), parse_mode=ParseMode.HTML, reply_markup=_keyboard("solo") if not finished else None)
    await _preview(q.get_bot(), chat_id, result, f"🏏 <b>{result if isinstance(result, int) else 'WICKET'}</b> · {name}")
    if state["runs"] >= state["target"]:
        await _preview(q.get_bot(), chat_id, "win")


async def _duel(q, chat_id: int, uid: int, shot: str) -> None:
    key = f"mc2:duel:{chat_id}"
    state = await storage.load(key, None)
    if not isinstance(state, dict):
        await q.edit_message_text("🌘 That duel has expired. Start another /cricketduel.")
        return
    if state.get("turn") != uid:
        await q.answer("Not your ball 😭", show_alert=True)
        return

    # In innings 1, A bats. In innings 2, B bats. The non-batter never gets a
    # shot callback, which fixes the old alternating-turn bug during the chase.
    batter_id = state["a"] if state["innings"] == 1 else state["b"]
    if uid != batter_id:
        await q.answer("You're fielding this ball 🌙", show_alert=True)
        return
    batter = "a" if batter_id == state["a"] else "b"
    emoji, name, outcomes, risk = SHOTS[shot]
    balls_key, runs_key, wickets_key = f"balls_{batter}", f"runs_{batter}", f"wickets_{batter}"
    state[balls_key] += 1
    if random.random() > risk:
        state[wickets_key] += 1
        result: int | str = "wicket"
        state["commentary"] = f"{emoji} {name} — <b>WICKET.</b>"
    else:
        result = random.choice(outcomes)
        state[runs_key] += result
        state["commentary"] = f"{emoji} {name} — <b>{result}</b> run{'s' if result != 1 else ''}."

    innings_over = state[balls_key] >= 6 or state[wickets_key] >= 2
    if state["innings"] == 1 and innings_over:
        state["innings"] = 2
        state["turn"] = state["b"]
        state["commentary"] = f"☀️ First innings done: <b>{state['runs_a']}/{state['wickets_a']}</b>. {state['b']} begins the chase."
    elif state["innings"] == 2:
        target = state["runs_a"]
        chase_complete = state["runs_b"] >= target
        if chase_complete or innings_over:
            state["turn"] = None
        else:
            state["turn"] = state["b"]
    else:
        state["turn"] = state["a"]

    winner = None
    if state["turn"] is None:
        if state["runs_b"] > state["runs_a"]:
            winner = state["b"]
        elif state["runs_a"] > state["runs_b"]:
            winner = state["a"]
        else:
            winner = 0
        names = {state["a"]: "𝐁𝐀𝐓𝐓𝐄𝐑 𝐀", state["b"]: "𝐁𝐀𝐓𝐓𝐄𝐑 𝐁"}
        state["commentary"] = "🏆 <b>DRAW.</b> Both sides finish level." if winner == 0 else f"🏆 <b>{names[winner]} WINS.</b> The crease has spoken."

    await storage.set(key, state, ttl=1800)
    label = f"{state['runs_a']}/{state['wickets_a']}  🆚  {state['runs_b']}/{state['wickets_b']}"
    text = f"<b>⚔️ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐃𝐔𝐄𝐋</b>\n\n{label}\n\n<i>{state['commentary']}</i>"
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=_keyboard("duel") if state["turn"] else None)
    await _preview(q.get_bot(), chat_id, result, f"🏏 <b>{result if isinstance(result, int) else 'WICKET'}</b> · {name}")
    if winner not in (None, 0):
        await _preview(q.get_bot(), chat_id, "win")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":", 2)
    if len(parts) != 3:
        return
    _, game, shot = parts
    if shot not in SHOTS:
        return
    if game == "solo":
        await _solo(q, q.message.chat.id, q.from_user.id, shot)
    elif game == "duel":
        await _duel(q, q.message.chat.id, q.from_user.id, shot)


def install(application) -> None:
    application.add_handler(CommandHandler(["cricket", "cricketgame"], cricket), group=16)
    application.add_handler(CommandHandler(["cricketduel", "cricketvs"], cricketduel), group=16)
    application.add_handler(CallbackQueryHandler(callback, pattern=r"^mc2:"), group=16)
