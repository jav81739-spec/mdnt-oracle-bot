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
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

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



async def _cricket_replay(bot, chat_id: int, term: str, caption: str) -> bool:
    """Game-only media: one action clip with the ball-by-ball commentary."""
    try:
        from handlers.chat import get_gif_url
        url = await get_gif_url(term)
        if not url:
            return False
        await bot.send_animation(chat_id=chat_id, animation=url, caption=caption[:1024],
                                  parse_mode=ParseMode.HTML)
        return True
    except Exception:
        return False


CRICKET_SHOT_TERMS = {
    "defend": "cricket batsman defensive shot live action",
    "cover": "cricket cover drive live action",
    "cut": "cricket square cut live action",
    "sweep": "cricket sweep shot live action",
    "pull": "cricket pull shot live action",
    "hook": "cricket hook shot live action",
    "loft": "cricket lofted drive live action",
    "straight": "cricket straight drive live action",
    "helicopter": "cricket helicopter shot live action",
    "reverse": "cricket reverse sweep live action",
}

CRICKET_BOWL_TERMS = (
    "cricket fast bowler delivery live action",
    "cricket bowler wicket delivery live action",
    "cricket pace bowling action live",
    "cricket spin bowling delivery live action",
)


async def _cricket_ball_media(bot, chat_id: int, shot_key: str, *,
                              batter: str, bowler: str, outcome: str, runs: int = 0) -> None:
    if outcome == "wicket":
        term = random.choice(CRICKET_BOWL_TERMS)
        line = f"🎙️ <b>{html.escape(bowler)}</b> runs in... {html.escape(batter)} is beaten! <b>WICKET!</b>"
    else:
        term = CRICKET_SHOT_TERMS.get(shot_key, "cricket batting shot live action")
        if runs == 6:
            line = f"🎙️ <b>{html.escape(batter)}</b> gets underneath it... <b>SIX!</b> Clean over the rope."
        elif runs == 4:
            line = f"🎙️ <b>{html.escape(batter)}</b> opens the face... <b>FOUR!</b> That's beautifully timed."
        else:
            line = f"🎙️ <b>{html.escape(batter)}</b> picks the gap... <b>{runs}</b> run{'s' if runs != 1 else ''}."
    caption = f"🏏 <b>LIVE FROM MIDNIGHT</b>\n\n{line}\n\n<i>{html.escape(outcome.title())} · ball by ball</i>"
    await _cricket_replay(bot, chat_id, term, caption)


CRICKET_MEDIA = {
    "defend": "cricket defensive shot live action",
    "cover": "cricket cover drive live action",
    "cut": "cricket square cut live action",
    "sweep": "cricket sweep shot live action",
    "pull": "cricket pull shot live action",
    "hook": "cricket hook shot live action",
    "loft": "cricket lofted drive live action",
    "straight": "cricket straight drive live action",
    "helicopter": "cricket helicopter shot live action",
    "reverse": "cricket reverse sweep live action",
}
CRICKET_BOWL_MEDIA = (
    "cricket fast bowler delivery live action",
    "cricket spin bowler delivery live action",
    "cricket wicket bowling live action",
    "cricket bowler celebration live action",
)


def _cricket_markup(chat_id: int, phase: str = "join") -> InlineKeyboardMarkup:
    rows = []
    if phase == "join":
        rows.append([InlineKeyboardButton("🏏 JOIN", callback_data=f"nightcricket:join:{chat_id}")])
        rows.append([InlineKeyboardButton("🪙 HEADS", callback_data=f"nightcricket:toss:heads:{chat_id}"),
                     InlineKeyboardButton("🪙 TAILS", callback_data=f"nightcricket:toss:tails:{chat_id}")])
    elif phase == "bat":
        rows.append([InlineKeyboardButton(str(n), callback_data=f"nightcricket:bat:{n}:{chat_id}") for n in range(1, 4)])
        rows.append([InlineKeyboardButton(str(n), callback_data=f"nightcricket:bat:{n}:{chat_id}") for n in range(4, 7)])
    return InlineKeyboardMarkup(rows)


async def _send_cricket_media(bot, chat_id: int, term: str, caption: str) -> None:
    try:
        from handlers.chat import get_gif_url
        url = await get_gif_url(term)
        if url:
            await bot.send_animation(chat_id=chat_id, animation=url, caption=caption[:1024], parse_mode=ParseMode.HTML)
            return
    except Exception:
        pass
    await bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)


def _cricket_caption(batter: str, bowler: str, shot: str, bowl: int, bat: int) -> tuple[str, str]:
    if bat == bowl:
        return (
            CRICKET_BOWL_MEDIA[bowl % len(CRICKET_BOWL_MEDIA)],
            f"🎙️ <b>{html.escape(bowler)}</b> comes in... {html.escape(batter)} commits — <b>WICKET!</b>\n"
            f"<i>Bowled {bowl}, batted {bat}. The numbers met.</i>",
        )
    runs = bat
    term = CRICKET_MEDIA.get(shot, "cricket batting shot live action")
    if runs == 6:
        call = f"🎙️ <b>{html.escape(batter)}</b> gets underneath it... <b>SIX!</b> That has gone miles."
    elif runs == 4:
        call = f"🎙️ <b>{html.escape(batter)}</b> finds the gap... <b>FOUR!</b> Beautifully timed."
    else:
        call = f"🎙️ <b>{html.escape(batter)}</b> picks it up... <b>{runs}</b> run{'s' if runs != 1 else ''}."
    return term, call + f"\n<i>Bowled {bowl}, batted {bat}.</i>"


CRICKET_MEDIA = {
    "defend": "cricket defensive shot live action",
    "cover": "cricket cover drive live action",
    "cut": "cricket square cut live action",
    "sweep": "cricket sweep shot live action",
    "pull": "cricket pull shot live action",
    "hook": "cricket hook shot live action",
    "loft": "cricket lofted drive live action",
    "straight": "cricket straight drive live action",
    "helicopter": "cricket helicopter shot live action",
    "reverse": "cricket reverse sweep live action",
}
CRICKET_BOWL_MEDIA = (
    "cricket fast bowler delivery live action",
    "cricket spin bowler delivery live action",
    "cricket wicket bowling live action",
    "cricket bowler celebration live action",
)


def _lobby_markup(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌙 JOIN MOON XI", callback_data=f"nightcricket:team:A:{chat_id}"),
         InlineKeyboardButton("☀️ JOIN SUN XI", callback_data=f"nightcricket:team:B:{chat_id}")],
        [InlineKeyboardButton("🪙 HEADS", callback_data=f"nightcricket:toss:heads:{chat_id}"),
         InlineKeyboardButton("🪙 TAILS", callback_data=f"nightcricket:toss:tails:{chat_id}")],
    ])


def _bat_markup(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(n), callback_data=f"nightcricket:bat:{n}:{chat_id}") for n in range(1, 4)],
        [InlineKeyboardButton(str(n), callback_data=f"nightcricket:bat:{n}:{chat_id}") for n in range(4, 7)],
    ])


async def _send_cricket_media(bot, chat_id: int, term: str, caption: str) -> None:
    try:
        from handlers.chat import get_gif_url
        url = await get_gif_url(term)
        if url:
            await bot.send_animation(chat_id=chat_id, animation=url, caption=caption[:1024], parse_mode=ParseMode.HTML)
            return
    except Exception:
        pass
    await bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)


async def _ask_bowler(bot, state: dict) -> None:
    bowler = int(state["bowler"])
    await storage.set(f"nightcricket:bowler:{bowler}", {"chat_id": int(state["chat_id"])}, ttl=300)
    try:
        await bot.send_message(
            chat_id=bowler,
            text="<b>🏏 NIGHT CRICKET · PRIVATE BALL</b>\n\n"
                 "You are bowling now.\n"
                 "Send me <b>one number: 1–6</b>.\n\n"
                 "<i>Your delivery stays hidden until the batter commits.</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


async def _start_ball(bot, state: dict) -> None:
    batting = state["teams"][state["batting_team"]]
    bowling = state["teams"][state["bowling_team"]]
    state["batter"] = batting[state["bat_idx"] % len(batting)]
    state["bowler"] = bowling[state["bowl_idx"] % len(bowling)]
    state["phase"] = "bowler_dm"
    await storage.set(f"nightcricket:match:{state['chat_id']}", state, ttl=3600)
    await _ask_bowler(bot, state)
    await bot.send_message(
        chat_id=int(state["chat_id"]),
        text=f"🌑 <b>BALL {state['ball'] + 1}/6</b>\n\n"
             f"Bowler: <b>{html.escape(state['names'].get(str(state['bowler']), 'Bowler'))}</b> — private call sent.\n"
             f"Batter: <b>{html.escape(state['names'].get(str(state['batter']), 'Batter'))}</b>\n\n"
             "<i>Wait for the delivery. Then choose your number.</i>",
        parse_mode=ParseMode.HTML,
    )


async def nightcricket(update, context) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or chat.type not in {"group", "supergroup"}:
        await update.effective_message.reply_text(
            "🏏 <b>Night Cricket belongs in the group.</b>\nStart it from a group chat.",
            parse_mode=ParseMode.HTML,
        )
        return
    key = f"nightcricket:match:{chat.id}"
    old = await storage.load(key, None)
    if isinstance(old, dict) and old.get("phase") not in {"finished", None}:
        await update.effective_message.reply_text("🏏 <b>This ground already has a match.</b>\nFinish it before opening another.", parse_mode=ParseMode.HTML)
        return
    state = {
        "chat_id": chat.id, "captain": user.id,
        "teams": {"A": [user.id], "B": []},
        "captains": {"A": user.id, "B": None},
        "names": {str(user.id): user.first_name or "Captain"},
        "phase": "lobby", "toss": None, "toss_winner": None,
        "batting_team": None, "bowling_team": None,
        "batter": None, "bowler": None, "bat_idx": 0, "bowl_idx": 0,
        "ball": 0, "runs": 0, "wickets": 0,
    }
    await storage.set(key, state, ttl=3600)
    await update.effective_message.reply_text(
        "<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\n"
        "<i>The group becomes the ground.</i>\n"
        "──────────────\n"
        f"👑 Moon XI Captain: <b>{html.escape(user.first_name or 'Captain')}</b>\n"
        "☀️ Sun XI needs a captain — the first player to join Sun XI becomes one.\n\n"
        "<b>Join a side:</b> 🌙 Moon XI or ☀️ Sun XI\n"
        "<b>Then:</b> captain calls Heads/Tails.\n\n"
        "<i>Two teams. Two captains. One over.</i>",
        parse_mode=ParseMode.HTML, reply_markup=_lobby_markup(chat.id),
    )


async def nightcricket_dm(update, context) -> None:
    chat, user, msg = update.effective_chat, update.effective_user, update.effective_message
    if not chat or chat.type != "private" or not user or not msg:
        return
    choice = (msg.text or "").strip()
    if choice not in {"1", "2", "3", "4", "5", "6"}:
        return
    ticket = await storage.load(f"nightcricket:bowler:{user.id}", None)
    if not isinstance(ticket, dict):
        return
    key = f"nightcricket:match:{int(ticket.get('chat_id', 0))}"
    state = await storage.load(key, None)
    if not isinstance(state, dict) or state.get("phase") != "bowler_dm" or state.get("bowler") != user.id:
        return
    state["bowl"] = int(choice)
    state["phase"] = "batting"
    await storage.set(key, state, ttl=3600)
    await storage.delete(f"nightcricket:bowler:{user.id}")
    await context.bot.send_message(
        chat_id=state["chat_id"],
        text=f"🌑 <b>DELIVERY LOCKED.</b>\n\n"
             f"<b>{html.escape(state['names'].get(str(state['batter']), 'Batter'))}</b> — your number. Pick <b>1–6</b>.",
        parse_mode=ParseMode.HTML, reply_markup=_bat_markup(int(state["chat_id"])),
    )


async def nightcricket_group_text(update, context) -> None:
    msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not msg or not chat or chat.type not in {"group", "supergroup"} or not user:
        return
    text = (msg.text or "").strip().lower()
    if text not in {"bat", "bowl"}:
        return
    key = f"nightcricket:match:{chat.id}"
    state = await storage.load(key, None)
    if not isinstance(state, dict) or state.get("phase") != "choice" or state.get("toss_winner") != user.id:
        return
    state["batting_team"] = "A" if text == "bat" and state["toss_winner"] == state["captains"]["A"] else ("B" if text == "bat" else "A")
    if text == "bowl":
        state["bowling_team"] = state["batting_team"]
        state["batting_team"] = "B" if state["batting_team"] == "A" else "A"
    else:
        state["bowling_team"] = "B" if state["batting_team"] == "A" else "A"
    state["phase"] = "starting"
    await storage.set(key, state, ttl=3600)
    await update.effective_message.reply_text(
        f"🏏 <b>{' '.join([text.upper()])}</b> it is.\n\n"
        f"Batting: <b>{state['batting_team']} XI</b>\nBowling: <b>{state['bowling_team']} XI</b>\n\n"
        "<i>First ball is loading. Bowler, check your DM.</i>",
        parse_mode=ParseMode.HTML,
    )
    await _start_ball(context.bot, state)


async def nightcricket_callback(update, context) -> None:
    q = update.callback_query
    if not q or not q.message or not q.from_user:
        return
    await q.answer()
    parts = (q.data or "").split(":")
    if len(parts) < 3 or parts[0] != "nightcricket":
        return
    action = parts[1]
    chat_id = int(parts[-1]) if parts[-1].lstrip("-").isdigit() else q.message.chat.id
    key = f"nightcricket:match:{chat_id}"
    state = await storage.load(key, None)
    if not isinstance(state, dict):
        await q.message.reply_text("🌘 That match has gone cold. Start /nightcricket again.")
        return
    uid = q.from_user.id

    if action == "team" and len(parts) >= 4:
        team = parts[2]
        if team not in {"A", "B"}:
            return
        if uid in state["teams"]["A"] or uid in state["teams"]["B"]:
            await q.answer("You're already on a team.", show_alert=True)
            return
        state["teams"][team].append(uid)
        state["names"][str(uid)] = q.from_user.first_name or "Player"
        if team == "B" and state["captains"]["B"] is None:
            state["captains"]["B"] = uid
        await storage.set(key, state, ttl=3600)
        await q.message.reply_text(
            f"🏏 <b>{html.escape(q.from_user.first_name or 'Player')}</b> joined {'🌙 Moon XI' if team == 'A' else '☀️ Sun XI'}."
            + (f"\n👑 Sun XI Captain: <b>{html.escape(q.from_user.first_name or 'Captain')}</b>" if team == "B" and state["captains"]["B"] == uid else ""),
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "toss":
        if uid != state["captain"]:
            await q.answer("Only the Moon XI captain calls the toss.", show_alert=True)
            return
        if not state["teams"]["B"] or not state["captains"]["B"]:
            await q.answer("Sun XI needs players first.", show_alert=True)
            return
        result = random.choice(("heads", "tails"))
        choice = parts[2].lower()
        winner = state["captains"]["A"] if choice == result else state["captains"]["B"]
        state["toss"], state["toss_winner"], state["phase"] = result, winner, "choice"
        await storage.set(key, state, ttl=3600)
        await q.message.reply_text(
            f"🪙 <b>{result.upper()}</b>.\n\n"
            f"👑 <b>{html.escape(state['names'].get(str(winner), 'Captain'))}</b> won the toss.\n"
            "<i>Winning captain: type <b>BAT</b> or <b>BOWL</b> in the group.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "bat" and len(parts) >= 3:
        if state.get("phase") != "batting" or uid != state.get("batter"):
            await q.answer("Not your turn.", show_alert=True)
            return
        bat = int(parts[2])
        if not 1 <= bat <= 6:
            return
        bowl = int(state.get("bowl", 0))
        state["ball"] += 1
        if bat == bowl:
            state["wickets"] += 1
            term = random.choice(CRICKET_BOWL_MEDIA)
            caption = f"🎙️ <b>{html.escape(state['names'].get(str(state['bowler']), 'Bowler'))}</b> comes in... {html.escape(state['names'].get(str(state['batter']), 'Batter'))} is beaten — <b>WICKET!</b>"
        else:
            state["runs"] += bat
            shot = random.choice(tuple(CRICKET_MEDIA))
            term = CRICKET_MEDIA[shot]
            caption = f"🎙️ <b>{html.escape(state['names'].get(str(state['batter']), 'Batter'))}</b> finds the gap... <b>{'SIX!' if bat == 6 else 'FOUR!' if bat == 4 else str(bat) + ' RUNS!'}</b>"
        await storage.set(key, state, ttl=3600)
        await _send_cricket_media(context.bot, chat_id, term, f"🏏 <b>LIVE FROM MIDNIGHT</b>\n\n{caption}\n\n<i>Bowled {bowl} · Batted {bat}</i>")
        if state["ball"] >= 6 or state["wickets"] >= 2:
            state["phase"] = "finished"
            await storage.set(key, state, ttl=900)
            await q.message.reply_text(
                f"<b>🏏 INNINGS CLOSED</b>\n\n<b>{state['runs']}/{state['wickets']}</b> · {state['ball']} balls\n"
                f"🌙 Moon XI vs ☀️ Sun XI\n\n<i>One over. One memory.</i>",
                parse_mode=ParseMode.HTML,
            )
            return
        state["bat_idx"] += 1
        state["bowl_idx"] += 1
        await _start_ball(context.bot, state)

def _existing(app):
    return {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}


def register(app):
    existing = _existing(app)
    # These are the only commands found in V2 history without an owner in
    # final-integration. Do not shadow the legacy bond/signal/cricket handlers.
    for command, callback in (
        ("oraclepair", oraclepair), ("vow", vow), ("mprofile", mprofile),
        ("achievements", achievements), ("midnightevent", midnightevent),
        ("cricketduel", cricketduel), ("nightcricket", nightcricket),
    ):
        if command not in existing:
            app.add_handler(CommandHandler(command, callback), group=16); existing.add(command)
    if not any(getattr(h, "callback", None) is cricket_callback for hs in getattr(app, "handlers", {}).values() for h in hs):
        app.add_handler(CallbackQueryHandler(cricket_callback, pattern=r"^v2cricket:"), group=16)
    app.add_handler(CallbackQueryHandler(nightcricket_callback, pattern=r"^nightcricket:"), group=16)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, nightcricket_dm), group=16)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, nightcricket_group_text), group=16)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, nightcricket_dm), group=16)
