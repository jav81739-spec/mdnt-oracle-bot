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


async def nightcricket(update, context) -> None:
    """Midnight's cricket room: original six-ball arcade, with optional action media."""
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏏 SOLO · 6 BALLS", callback_data="nightcricket:quick")],
        [InlineKeyboardButton("⚔️ DUEL", callback_data="nightcricket:duel"),
         InlineKeyboardButton("🎯 SHOT LAB", callback_data="nightcricket:shots")],
        [InlineKeyboardButton("✦ HOW IT PLAYS", callback_data="nightcricket:help")],
    ])
    await update.effective_message.reply_text(
        "<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓</b>\n\n"
        "<i>Read the risk. Pick the shot.</i>\n"
        "──────────────\n"
        "A six-ball cricket room where every choice has a consequence.\n\n"
        "<b>SOLO</b> · face the Oracle\n"
        "<b>DUEL</b> · face someone in the room\n"
        "<b>SHOT LAB</b> · study the shots\n\n"
        "<code>no coins · no farming · just cricket</code>",
        parse_mode=ParseMode.HTML, reply_markup=markup,
    )


async def nightcricket_callback(update, context) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return
    await query.answer()
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "quick":
        state = {"uid": query.from_user.id, "runs": 0, "balls": 0, "wickets": 0}
        key = f"nightcricket:solo:{query.message.chat.id}:{query.from_user.id}"
        await storage.set(key, state, ttl=1800)
        buttons = [
            [InlineKeyboardButton(str(n), callback_data=f"nightcricket:ball:{n}") for n in range(1, 4)],
            [InlineKeyboardButton(str(n), callback_data=f"nightcricket:ball:{n}") for n in range(4, 7)],
        ]
        await query.message.reply_text(
            "<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐁𝐀𝐋𝐋 𝟏/𝟔</b>\n\n"
            "<i>You bat. The Oracle bowls.</i>\n\n"
            "Pick <b>1–6</b>. Match the delivery and you're gone. Miss it and your number becomes the runs.\n\n"
            "<code>Choose like you mean it.</code>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if action == "ball" and len(parts) == 3 and parts[2].isdigit():
        choice = int(parts[2])
        if not 1 <= choice <= 6:
            return
        key = f"nightcricket:solo:{query.message.chat.id}:{query.from_user.id}"
        state = await storage.load(key, None)
        if not isinstance(state, dict) or state.get("uid") != query.from_user.id:
            await query.message.reply_text("🌘 That innings has gone cold. Use /nightcricket to begin again.")
            return
        bowl = random.randint(1, 6)
        state["balls"] += 1
        if choice == bowl:
            state["wickets"] += 1
            await storage.set(key, state, ttl=1800)
            await _cricket_ball_media(context.bot, query.message.chat.id, "defend",
                                      batter=query.from_user.first_name or "Batter",
                                      bowler="the Oracle", outcome="wicket")
        else:
            state["runs"] += choice
            await storage.set(key, state, ttl=1800)
            shot = random.choice(tuple(CRICKET_SHOT_TERMS))
            await _cricket_ball_media(context.bot, query.message.chat.id, shot,
                                      batter=query.from_user.first_name or "Batter",
                                      bowler="the Oracle", outcome="runs", runs=choice)

        if state["balls"] >= 6 or state["wickets"] >= 2:
            result = "🔥 <b>INNINGS CLOSED.</b>" if state["wickets"] < 2 else "💀 <b>TWO WICKETS. INNINGS OVER.</b>"
            await query.message.reply_text(
                f"<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐅𝐈𝐍𝐈𝐒𝐇𝐄𝐃</b>\n\n"
                f"<b>{state['runs']}/{state['wickets']}</b> · {state['balls']} balls\n\n"
                f"{result}\n<i>Come back when you want another over.</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        next_ball = state["balls"] + 1
        buttons = [
            [InlineKeyboardButton(str(n), callback_data=f"nightcricket:ball:{n}") for n in range(1, 4)],
            [InlineKeyboardButton(str(n), callback_data=f"nightcricket:ball:{n}") for n in range(4, 7)],
        ]
        await query.message.reply_text(
            f"<b>🏏 𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐈𝐂𝐊𝐄𝐓 · 𝐁𝐀𝐋𝐋 {next_ball}/6</b>\n\n"
            f"<b>{state['runs']}/{state['wickets']}</b>\n\n"
            "<i>Next ball. Read the risk.</i>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if action == "duel":
        await query.message.reply_text(
            "⚔️ <b>DUEL READY</b>\n\nReply to a member with <code>/cricketduel</code>.\n"
            "<i>Six balls. No coins. Bragging rights only.</i>",
            parse_mode=ParseMode.HTML,
        )
    elif action == "shots":
        lines = [
            f"{icon} <b>{name}</b> · {int(risk * 100)}% control · {','.join(map(str, outcomes))} runs"
            for _, (icon, name, outcomes, risk) in SHOTS.items()
        ]
        await query.message.reply_text(
            "<b>🎯 𝐒𝐇𝐎𝐓 𝐋𝐀𝐁</b>\n\n" + "\n".join(lines) +
            "\n\n<i>Every shot has its own risk. The clips follow the shot you play.</i>",
            parse_mode=ParseMode.HTML,
        )
    elif action == "help":
        await query.message.reply_text(
            "<b>✦ 𝐇𝐎𝐖 𝐈𝐓 𝐏𝐋𝐀𝐘𝐒</b>\n\n"
            "You bat for six balls.\n"
            "Pick <b>1–6</b>. The Oracle secretly bowls <b>1–6</b>.\n"
            "Match = wicket. No match = your chosen number in runs.\n\n"
            "Every ball can return a shot/bowling action clip with a live-style commentary line.\n\n"
            "<i>It should feel like a tiny cricket broadcast inside the group — without pretending to be an actual live match.</i> ☾",
            parse_mode=ParseMode.HTML,
        )



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
