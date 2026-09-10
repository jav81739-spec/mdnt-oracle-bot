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


async def nightcricket(update, context) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in {"group", "supergroup"}:
        await update.effective_message.reply_text("🏏 <b>Night Cricket belongs in the group.</b>\nStart it from a group chat.", parse_mode=ParseMode.HTML)
        return
    key = f"nightcricket:match:{chat.id}"
    state = await storage.load(key, None)
    if isinstance(state, dict) and state.get("phase") not in {"finished", None}:
        await update.effective_message.reply_text("🏏 <b>Night Cricket is already running here.</b>\nJoin the current room or let its captain finish it.", parse_mode=ParseMode.HTML)
        return
    state = {
        "chat_id": chat.id, "captain": user.id, "players": [user.id],
        "names": {str(user.id): user.first_name or "Captain"}, "phase": "lobby",
        "toss": None, "batting": None, "bowling": None, "ball": 0,
        "runs": 0, "wickets": 0, "last_shot": "cover",
    }
    await storage.set(key, state, ttl=3600)
    await update.effective_message.reply_text(
        "<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\n"
        "<i>The group becomes the ground.</i>\n"
        "──────────────\n"
        f"👑 Captain: <b>{html.escape(user.first_name or 'Captain')}</b>\n"
        "Tap <b>JOIN</b> to enter. The captain calls the toss.\n\n"
        "<i>Heads or tails decides who gets first choice: bat or bowl.</i>",
        parse_mode=ParseMode.HTML, reply_markup=_cricket_markup(chat.id, "join"),
    )


async def nightcricket_dm(update, context) -> None:
    """Receives the bowler's private 1–6 delivery before the group sees the ball."""
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    if not chat or chat.type != "private" or not user or not msg:
        return
    text = (msg.text or "").strip()
    if text not in {"1", "2", "3", "4", "5", "6"}:
        return
    matches = await storage.load(f"nightcricket:bowler:{user.id}", None)
    if not isinstance(matches, dict):
        return
    match_key = f"nightcricket:match:{int(matches.get('chat_id', 0))}"
    state = await storage.load(match_key, None)
    if not isinstance(state, dict) or state.get("phase") != "bowler_dm" or state.get("bowling") != user.id:
        return
    state["bowl"] = int(text)
    state["phase"] = "batting"
    await storage.set(match_key, state, ttl=3600)
    await storage.delete(f"nightcricket:bowler:{user.id}")
    await context.bot.send_message(
        chat_id=state["chat_id"],
        text="<b>🏏 BALL IS LOADED.</b>\n\n"
             f"<i>{html.escape(state['names'].get(str(state['bowling']), 'Bowler'))} has chosen the delivery.</i>\n"
             f"<b>{html.escape(state['names'].get(str(state['batting']), 'Batter'))}</b> — your turn. Pick <b>1–6</b>.",
        parse_mode=ParseMode.HTML, reply_markup=_cricket_markup(int(state["chat_id"]), "bat"),
    )


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
    if action == "join":
        if uid not in state["players"]:
            state["players"].append(uid)
            state["names"][str(uid)] = q.from_user.first_name or "Player"
            await storage.set(key, state, ttl=3600)
        await q.message.reply_text(
            f"🏏 <b>{html.escape(q.from_user.first_name or 'Player')}</b> is in.\n"
            f"<i>{len(state['players'])} player{'s' if len(state['players']) != 1 else ''} in the room. Captain controls the toss.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "toss":
        if uid != state["captain"]:
            await q.answer("Only the captain calls the toss.", show_alert=True)
            return
        choice = parts[2].lower()
        result = random.choice(("heads", "tails"))
        winner = uid if choice == result else next((p for p in state["players"] if p != uid), None)
        if winner is None:
            await q.message.reply_text("Need at least two players before the toss. 🏏")
            return
        state["toss"] = result
        state["toss_winner"] = winner
        state["phase"] = "choice"
        await storage.set(key, state, ttl=3600)
        await q.message.reply_text(
            f"🪙 <b>{result.upper()}</b>.\n\n"
            f"👑 <b>{html.escape(state['names'].get(str(winner), 'Captain'))}</b> won the toss.\n"
            "<i>Reply to this message with <b>BAT</b> or <b>BOWL</b>.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "bat":
        if state.get("phase") != "batting" or uid != state.get("batting"):
            await q.answer("Not your turn.", show_alert=True)
            return
        bat = int(parts[2])
        bowl = int(state["bowl"])
        state["ball"] += 1
        shot = random.choice(tuple(CRICKET_MEDIA))
        state["last_shot"] = shot
        if bat == bowl:
            state["wickets"] += 1
            outcome = "wicket"
        else:
            state["runs"] += bat
            outcome = "runs"
        term, caption = _cricket_caption(state["names"].get(str(uid), "Batter"),
                                         state["names"].get(str(state["bowling"]), "Bowler"),
                                         shot, bowl, bat)
        await storage.set(key, state, ttl=3600)
        await _send_cricket_media(context.bot, chat_id, term, f"🏏 <b>LIVE FROM MIDNIGHT</b>\n\n{caption}")
        if state["ball"] >= 6 or state["wickets"] >= 2:
            await q.message.reply_text(
                f"<b>🏏 INNINGS CLOSED</b>\n\n<b>{state['runs']}/{state['wickets']}</b> · {state['ball']} balls\n"
                "<i>Next innings / team mode is ready for the same group.</i>",
                parse_mode=ParseMode.HTML,
            )
            state["phase"] = "finished"
            await storage.set(key, state, ttl=900)
            return
        state["phase"] = "bowler_dm"
        await storage.set(key, state, ttl=3600)
        state_key = f"nightcricket:bowler:{state['bowling']}"
        await storage.set(state_key, {"chat_id": chat_id}, ttl=300)
        try:
            await context.bot.send_message(
                chat_id=state["bowling"],
                text="<b>🏏 NIGHT CRICKET · PRIVATE BALL</b>\n\n"
                     "You are bowling.\n"
                     "Send me <b>one number: 1–6</b>.\n\n"
                     "<i>Your number stays private until the batsman commits.</i>",
                parse_mode=ParseMode.HTML,
            )
            await q.message.reply_text(
                "🌑 <b>The bowler has been sent the private call.</b>\n"
                "<i>Batsman, wait. The delivery is being loaded.</i>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await q.message.reply_text(
                "⚠️ <b>Bowler DM is not open.</b>\n"
                "The bowler must start a private chat with Midnight first, then continue the match.",
                parse_mode=ParseMode.HTML,
            )
        return



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
