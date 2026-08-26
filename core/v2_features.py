"""Midnight Oracle V2 feature pack.

Original Midnight-native social/relationship and cricket experiences, plus
persistent identity/progression and rare world events.
"""
from __future__ import annotations

import random
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from .storage import storage
from .midnight_world import install as install_world


def _mention(user) -> str:
    name = (user.first_name or "Midnight Soul").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def _target(update: Update):
    reply = update.effective_message.reply_to_message if update.effective_message else None
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return None

BOND_LINES = [
    ("✦ 𝐓𝐇𝐄 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐁𝐎𝐍𝐃 ✦", "Two names crossed the same page tonight."),
    ("☾ 𝐀 𝐐𝐔𝐈𝐄𝐓 𝐏𝐀𝐈𝐑𝐈𝐍𝐆 ☽", "The Oracle found an interesting combination."),
    ("𖤓 𝐍𝐈𝐆𝐇𝐓 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 𖤓", "Not destiny. Just a very suspiciously good pairing."),
]

async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    if target is None:
        await update.effective_message.reply_text("☾ <b>𝐁𝐎𝐍𝐃 𝐑𝐈𝐓𝐔𝐀𝐋</b>\n\nReply to someone's message and let the Oracle test the pairing.", parse_mode=ParseMode.HTML)
        return
    me = update.effective_user
    if target.id == me.id:
        await update.effective_message.reply_text("🌘 The Oracle refuses to pair you with your own reflection.", parse_mode=ParseMode.HTML); return
    score = random.randint(34, 98); title, line = random.choice(BOND_LINES)
    await update.effective_message.reply_text(f"<b>{title}</b>\n\n{_mention(me)} × {_mention(target)}\n\n<i>{line}</i>\n\n<b>𝐍𝐈𝐆𝐇𝐓 𝐒𝐘𝐍𝐂</b> · <b>{score}%</b>\n\n<i>For fun. The Oracle does not know either person's real feelings.</i> 🌙", parse_mode=ParseMode.HTML)

async def oraclepair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    members = await _recent_members(update.effective_chat.id)
    if len(members) < 2:
        await update.effective_message.reply_text("☾ I need at least two recently active souls before I can choose."); return
    a, b = random.sample(members, 2); score = random.randint(41, 99)
    await update.effective_message.reply_text("<b>✦ 𝐓𝐇𝐄 𝐎𝐑𝐀𝐂𝐋𝐄 𝐂𝐇𝐎𝐒𝐄𝐒 ✦</b>\n\n" f"{_mention(a)} × {_mention(b)}\n\n<b>{score}% 𝐍𝐈𝐆𝐇𝐓 𝐒𝐘𝐍𝐂</b>\n\n<i>No nominations. No applications. Just tonight's fictional pairing.</i> 🌙", parse_mode=ParseMode.HTML)

async def bondvow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    if target is None:
        await update.effective_message.reply_text("☾ Reply to a member to open a Midnight Vow."); return
    rule = random.choice(["No disappearing mid-conversation.", "One honest answer each.", "Choose the song for the other.", "Make each other laugh once."])
    await update.effective_message.reply_text("<b>𖤓 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐕𝐎𝐖 𖤓</b>\n\n" f"{_mention(update.effective_user)} × {_mention(target)}\n\n<i>Tonight's rule:</i> <b>{rule}</b>\n\n<i>Purely a group-game ritual.</i> ✦", parse_mode=ParseMode.HTML)

CRICKET_SHOTS = {
    "cover": ("🏏", "Cover Drive", 1, 0.72), "pull": ("🔥", "Pull Shot", 2, 0.58),
    "loft": ("🚀", "Lofted Hit", 3, 0.43), "defend": ("🛡️", "Dead Bat", 0, 0.88),
    "sweep": ("🌪️", "Sweep", 2, 0.62), "reverse": ("🌀", "Reverse", 4, 0.30),
}

async def _recent_members(chat_id: int):
    raw = await storage.load(f"autonomy:members:{chat_id}", {})
    if not isinstance(raw, dict): return []
    cutoff = time.time() - 48 * 3600; users = []
    for item in raw.values():
        try:
            if float(item["seen"]) < cutoff: continue
            class U: pass
            u = U(); u.id = int(item["user_id"]); u.first_name = str(item.get("name") or "Midnight Soul"); users.append(u)
        except (KeyError, TypeError, ValueError): continue
    return users

def _scorecard(state: dict[str, Any]) -> str:
    return f"🏏 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\nOver {state['over']}.{state['ball']} · {state['runs']}/{state['wickets']}\nTarget: {state.get('target', '—')} · Balls left: {state['balls_left']}\n\n<i>{state['commentary']}</i>"

def _shot_keyboard():
    buttons = [InlineKeyboardButton(f"{e} {n}", callback_data=f"mcr:shot:{k}") for k, (e, n, *_r) in CRICKET_SHOTS.items()]
    return InlineKeyboardMarkup([buttons[:3], buttons[3:]])

async def cricket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id; chat_id = update.effective_chat.id
    state = {"mode":"solo","uid":uid,"over":0,"ball":0,"runs":0,"wickets":0,"balls_left":12,"target":random.choice([24,29,34,41]),"commentary":"The night has opened the crease. Choose your shot."}
    await storage.set(f"cricket:game:{chat_id}:{uid}", state, ttl=1800)
    await update.effective_message.reply_text(_scorecard(state), parse_mode=ParseMode.HTML, reply_markup=_shot_keyboard())

async def cricketduel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target(update)
    if target is None: await update.effective_message.reply_text("🏏 Reply to a member's message with /cricketduel to challenge them."); return
    if target.id == update.effective_user.id: await update.effective_message.reply_text("🌙 You cannot bowl at your own shadow."); return
    chat_id = update.effective_chat.id
    state = {"mode":"duel","a":update.effective_user.id,"b":target.id,"runs_a":0,"runs_b":0,"balls":6,"turn":update.effective_user.id}
    await storage.set(f"cricket:duel:{chat_id}", state, ttl=1800)
    await update.effective_message.reply_text("<b>⚔️ 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 𝐍𝐈𝐆𝐇𝐓 — 𝐃𝐔𝐄𝐋</b>\n\n" f"{_mention(update.effective_user)} vs {_mention(target)}\n\n<i>Six balls. Skill beats the wallet. There is no economy reward.</i> 🏏", parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text("<b>First batter:</b> choose your shot.", parse_mode=ParseMode.HTML, reply_markup=_shot_keyboard())

async def cricket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query; await q.answer()
    if not q.data.startswith("mcr:shot:"): return
    shot = q.data.rsplit(":",1)[1]; chat_id = q.message.chat.id; uid = q.from_user.id
    key = f"cricket:game:{chat_id}:{uid}"; state = await storage.load(key, None)
    if not isinstance(state, dict): await q.edit_message_text("🌘 That crease has already gone quiet. Start a new /cricket game."); return
    if state.get("balls_left",0) <= 0 or state.get("wickets",0) >= 3: await q.edit_message_text(_scorecard(state), parse_mode=ParseMode.HTML); return
    emoji, name, base, risk = CRICKET_SHOTS[shot]; state["balls_left"] -= 1; state["ball"] += 1
    if state["ball"] >= 6: state["ball"] = 0; state["over"] += 1
    if random.random() > risk:
        state["wickets"] += 1; state["commentary"] = f"{emoji} {name} — <b>WICKET!</b> The Oracle saw the risk coming."
    else:
        runs = base + random.choice([0,0,1]); state["runs"] += runs; state["commentary"] = f"{emoji} {name} — <b>{runs} run{'s' if runs != 1 else ''}.</b> {random.choice(['clean timing.','that came off beautifully.','the night approves.','absolute cinema.'])}"
    if state["runs"] >= state["target"]: state["commentary"] = "🏆 <b>TARGET CHASED.</b> The crease belongs to you tonight."; state["balls_left"] = 0
    await storage.set(key, state, ttl=1800)
    await q.edit_message_text(_scorecard(state), parse_mode=ParseMode.HTML, reply_markup=_shot_keyboard() if state["balls_left"] else None)

UPGRADE = ("<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐑𝐀𝐂𝐋𝐄 — 𝐕𝟐 𝐇𝐄𝐋𝐏</b>\n\n"
"<i>V2 is a living engine, not a skin over V1.</i>\n\n"
"<b>✦ Social</b>\n/bond · /oraclepair · /vow\n\n"
"<b>🧬 Identity</b>\n/mprofile · /achievements\nYour title, archetype, XP, luck, chaos and marks evolve through play.\n\n"
"<b>🌑 World</b>\n/midnightevent\nRare events can change what the Oracle does next.\n\n"
"<b>🏏 Cricket</b>\n/cricket · /cricketduel\nA separate skill universe. No coin farming.\n\n"
"<b>🎧 Audio</b>\n/midnightplay <i>song</i>\nQueue music for VC when the assistant is configured.\n\n"
"<b>🌙 Autonomous Oracle</b>\nThe room can trigger social moments without anyone invoking a command.")

async def upgradehelp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(UPGRADE, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

def install(application) -> None:
    application.add_handler(CommandHandler(["bond","ship"], bond), group=20)
    application.add_handler(CommandHandler(["oraclepair","fatepair"], oraclepair), group=20)
    application.add_handler(CommandHandler(["vow","midnightvow"], bondvow), group=20)
    application.add_handler(CommandHandler(["cricket","cricketgame"], cricket), group=20)
    application.add_handler(CommandHandler(["cricketduel","cricketvs"], cricketduel), group=20)
    application.add_handler(CommandHandler(["upgradehelp","upgradhelp"], upgradehelp), group=20)
    application.add_handler(CallbackQueryHandler(cricket_callback, pattern=r"^mcr:shot:"), group=20)
    install_world(application)
