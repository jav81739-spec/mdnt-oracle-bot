"""Midnight V2 social layer.

Original interaction commands, group pulse/awakening, trigger words and
associated-channel reactions. Designed to feel Hinglish, visual and
Midnight-native without copying another bot's implementation.
"""
from __future__ import annotations

import html
import os
import random
import time
from typing import Iterable

from telegram import BotCommand, BotCommandScopeAllGroupChats, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from .storage import storage


# ----------------------------- language / visuals --------------------------
HINGLISH = [
    "kya scene hai? 🌙",
    "arre wah, raat interesting ho gayi 👀",
    "acha ji… Oracle ne notice kar liya.",
    "thoda sa chaos toh banta hai na? 🫠",
    "haan bhai, Midnight sun raha hai. ☾",
]

ACTIONS = {
    "hug": ("🫂", "HUG", ["warm sa hug delivered.", "idhar aa, ek proper hug banta hai.", "hug locked. no overthinking. 🌙"]),
    "kiss": ("💋", "KISS", ["a tiny Midnight kiss landed.", "mwah — bas itna hi allowed tonight. 💋", "Oracle-approved kiss. Don't get used to it. 😌"]),
    "pat": ("🫳", "PAT", ["pat pat. you'll be fine.", "head pat delivered with suspicious sincerity.", "pat received. ab drama thoda kam. 🌙"]),
    "kick": ("🦶", "KICK", ["a playful kick sent flying.", "bonk—wrong universe, same energy. 😭", "one dramatic kick. purely fictional. ⚡"]),
    "slap": ("🫲", "SLAP", ["playful slap detected. no real damage.", "*thappad.exe* — group-game mode only. 😭", "Midnight issued a cartoon-level slap."]),
    "punch": ("👊", "PUNCH", ["cartoon punch landed. zero real damage.", "POW! straight out of a comic panel. 💥", "one harmless dramatic punch."]),
    "highfive": ("🙌", "HIGH FIVE", ["clean high-five. ✋", "that one echoed through the timeline.", "high-five successful. team energy +1."]),
    "cuddle": ("🧸", "CUDDLE", ["cuddle mode: activated.", "soft corner unlocked. 🫂", "Midnight has temporarily banned loneliness."]),
    "poke": ("👉", "POKE", ["poke.", "POKE POKE. now you have to react. 👀", "a tiny disturbance has been detected."]),
    "bonk": ("🔨", "BONK", ["bonk. respectfully.", "BONK — go drink water. 😭", "the bonk was witnessed by the Oracle."]),
    "bite": ("🦷", "BITE", ["tiny fictional bite. no hospital required. 😭", "nom. blame the Oracle.", "Midnight has chosen chaos today."]),
    "wave": ("👋", "WAVE", ["a moonlit wave from Midnight.", "heyyy 👋", "wave received and returned. 🌙"]),
    "wink": ("😉", "WINK", ["one suspicious wink.", "Oracle saw that. 👀", "wink delivered. moving on before this gets awkward."]),
    "dance": ("🕺", "DANCE", ["the Oracle has entered dance mode.", "music on. dignity off. 🕺", "one completely unnecessary dance break."]),
    "roast": ("🔥", "ROAST", ["light roast only. Midnight has standards. 😭", "a tiny roast, perfectly toasted.", "the Oracle chose violence—but politely. 🔥"]),
}

ALIASES = {
    "hug": "hug", "kiss": "kiss", "pat": "pat", "kick": "kick", "slap": "slap",
    "punch": "punch", "highfive": "highfive", "high5": "highfive", "cuddle": "cuddle",
    "poke": "poke", "bonk": "bonk", "bite": "bite", "wave": "wave", "wink": "wink",
    "dance": "dance", "roast": "roast",
}


def _mention(user) -> str:
    name = html.escape(user.first_name or "Midnight Soul")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def _target(update: Update):
    msg = update.effective_message
    reply = msg.reply_to_message if msg else None
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return None


def _visual(action: str, actor, target) -> str:
    emoji, title, lines = ACTIONS[action]
    return (
        f"<b>━━━━━━━━━━━━━━━━</b>\n"
        f"<b>{emoji} 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 · {title}</b>\n\n"
        f"{_mention(actor)}  →  {_mention(target)}\n\n"
        f"<i>{random.choice(lines)}</i>\n\n"
        f"<code>☾ midnight interaction · just for fun</code>\n"
        f"<b>━━━━━━━━━━━━━━━━</b>"
    )


async def interaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = (update.effective_message.text or "").split()[0].lstrip("/").split("@")[0].lower()
    action = ALIASES.get(command)
    if not action:
        return
    target = _target(update)
    if target is None:
        await update.effective_message.reply_text(
            f"☾ <b>{ACTIONS[action][1]} RITUAL</b>\n\nReply to a member's message and use /{command}.\n\n<i>{random.choice(HINGLISH)}</i>",
            parse_mode=ParseMode.HTML,
        )
        return
    if target.id == update.effective_user.id:
        await update.effective_message.reply_text("🌘 khud ko target karke Oracle ko confuse mat karo 😭", parse_mode=ParseMode.HTML)
        return
    await update.effective_message.reply_text(_visual(action, update.effective_user, target), parse_mode=ParseMode.HTML)


# ----------------------------- group pulse --------------------------------
PULSE_ALIVE = 20 * 60
PULSE_DORMANT = 45 * 60
PULSE_DEAD = 3 * 60 * 60
AWAKEN_COOLDOWN = 6 * 60 * 60


def _member_key(chat_id: int, user_id: int) -> str:
    return f"v2:pulse:members:{chat_id}:{user_id}"


def _pulse_key(chat_id: int) -> str:
    return f"v2:pulse:{chat_id}"


async def observe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return
    user = update.effective_user
    if not user or user.is_bot:
        return
    chat_id = update.effective_chat.id
    now = time.time()
    pulse = await storage.load(_pulse_key(chat_id), {})
    if not isinstance(pulse, dict):
        pulse = {}
    pulse.update({"last_message": now, "messages": int(pulse.get("messages", 0)) + 1})
    await storage.set(_pulse_key(chat_id), pulse, ttl=8 * 24 * 3600)
    await storage.set(_member_key(chat_id, user.id), {"user_id": user.id, "name": user.first_name or "Midnight Soul", "seen": now}, ttl=8 * 24 * 3600)

    trigger = str(pulse.get("trigger") or os.getenv("MIDNIGHT_TRIGGER", "midnight")).strip().lower()
    text = (update.effective_message.text or update.effective_message.caption or "").strip().lower()
    words = {w.strip(".,!?;:()[]{}<>\"'`").lower() for w in text.split()}
    if trigger and trigger in words:
        await _trigger_reply(update, pulse)
        return

    # Only attempt an awakening on a new message after a genuine quiet period.
    # We observe activity rather than pretending Telegram exposes a full member list.
    if now - float(pulse.get("last_awakened", 0)) < AWAKEN_COOLDOWN:
        return
    previous = float(pulse.get("previous_message", pulse.get("last_message", now)))
    quiet_for = now - previous
    if quiet_for >= PULSE_DEAD:
        await _awaken(update, pulse, "dead")
    elif quiet_for >= PULSE_DORMANT:
        await _awaken(update, pulse, "dormant")
    pulse["previous_message"] = now
    await storage.set(_pulse_key(chat_id), pulse, ttl=8 * 24 * 3600)


async def _trigger_reply(update: Update, pulse: dict) -> None:
    now = time.time()
    if now - float(pulse.get("last_trigger", 0)) < 20:
        return
    pulse["last_trigger"] = now
    await storage.set(_pulse_key(update.effective_chat.id), pulse, ttl=8 * 24 * 3600)
    options = [
        "☾ <b>𝐓𝐇𝐄 𝐎𝐑𝐀𝐂𝐋𝐄 𝐈𝐒 𝐀𝐖𝐀𝐊𝐄</b>\n\nBol diya naam… ab bolo, kya scene hai? 👀",
        "🌙 <b>𝐘𝐎𝐔 𝐂𝐀𝐋𝐋𝐄𝐃?</b>\n\nHaan bhai, Midnight sun raha hai. Kya karna hai? 🫠",
        "✦ <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐄𝐒𝐏𝐎𝐍𝐃𝐒</b>\n\nMain yahin tha. Tum logon ne bulaya, ab chaos bhi tumhara. 😭",
        "🌘 <b>𝐎𝐑𝐀𝐂𝐋𝐄 𝐎𝐍𝐋𝐈𝐍𝐄</b>\n\nAcha… kisne mujhe yaad kiya? 👁️",
    ]
    await update.effective_message.reply_text(random.choice(options), parse_mode=ParseMode.HTML)


async def _awaken(update: Update, pulse: dict, state: str) -> None:
    now = time.time()
    pulse["last_awakened"] = now
    await storage.set(_pulse_key(update.effective_chat.id), pulse, ttl=8 * 24 * 3600)
    if state == "dead":
        lines = [
            "🌘 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐄𝐒𝐔𝐑𝐑𝐄𝐂𝐓𝐈𝐎𝐍</b>\n\nGroup itna shaant? 😭\n\n<code>Someone ask a cricket question.</code> 🏏",
            "🕯️ <b>𝐓𝐇𝐄 𝐑𝐎𝐎𝐌 𝐖𝐄𝐍𝐓 𝐐𝐔𝐈𝐄𝐓</b>\n\nOracle ko silence pasand hai… but itna bhi nahi.\n\n<b>Quick challenge:</b> first person to reply chooses tonight's chaos. 👀",
        ]
    else:
        lines = [
            "☾ <b>𝐐𝐔𝐈𝐄𝐓 𝐇𝐎𝐔𝐑</b>\n\nSab chup kyun hain? 😭\n\n< i >Ek random question se raat bacha lete hain.</i>",
            "🌙 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐏𝐈𝐍𝐆</b>\n\nRoom thoda quiet hai…\n\n<b>Pick one:</b> 🏏 cricket · 🎧 song · 🎮 game",
        ]
    await update.effective_message.reply_text(random.choice(lines), parse_mode=ParseMode.HTML)


# ----------------------------- admin trigger --------------------------------
async def settrigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    member = await update.effective_chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        await update.effective_message.reply_text("🌘 Sirf admins trigger set kar sakte hain.")
        return
    trigger = " ".join(context.args).strip().lower()
    if not trigger or len(trigger.split()) > 1 or len(trigger) > 32:
        await update.effective_message.reply_text("☾ Usage: /settrigger <one-word>")
        return
    pulse = await storage.load(_pulse_key(update.effective_chat.id), {})
    if not isinstance(pulse, dict): pulse = {}
    pulse["trigger"] = trigger
    await storage.set(_pulse_key(update.effective_chat.id), pulse, ttl=8 * 24 * 3600)
    await update.effective_message.reply_text(f"✦ Trigger set: <code>{html.escape(trigger)}</code>\n\nAb bas ye word bolo… Midnight pop out karega. 🌙", parse_mode=ParseMode.HTML)


# ----------------------------- channel reactions ---------------------------
def _channel_ids() -> set[int]:
    raw = os.getenv("MIDNIGHT_ASSOCIATED_CHANNELS", "")
    out: set[int] = set()
    for value in raw.split(","):
        try: out.add(int(value.strip()))
        except ValueError: pass
    return out


def _relevant_comment(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("cricket", "match", "innings", "wicket", "runs", "bcci", "ipl", "test", "odi", "t20")):
        return random.choice(["🏏 Ye update toh Midnight feed pe seedha boundary hai. 👀", "Cricket news spotted — ab group mein discussion pakka. 🏏🌙", "Oho, cricket timeline ne phir se scene interesting kar diya. 👁️🏏"])
    if any(k in t for k in ("win", "won", "victory", "champion", "trophy")):
        return random.choice(["🏆 Big moment. Isko Midnight archive mein jaana chahiye. 🌙", "Acha ji, victory energy detected. 👑", "This one deserves the celebration. 🔥"])
    if any(k in t for k in ("breaking", "announcement", "official", "confirmed")):
        return random.choice(["👀 Okay, this is actually important. Midnight has seen it.", "Confirmed? Ab scene serious hai. 🌙", "Breaking energy detected. Group ko ye dekhna padega. 👁️"])
    if any(k in t for k in ("good night", "gn", "night")):
        return random.choice(["🌙 Midnight-approved night post. Sleep well, legends.", "Raat officially registered. ☾✨", "Good night vibes received. Kal phir milte hain. 🌙"])
    return random.choice(["🌙 Ye post quietly deserved a Midnight reaction. 👀", "Acha post hai — Midnight ne notice kar liya. ✦", "Timeline pe ye wala moment rukne layak tha. 🌙"])


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    if not post or post.chat.id not in _channel_ids():
        return
    text = post.text or post.caption or ""
    comment = _relevant_comment(text)
    try:
        channel = await context.bot.get_chat(post.chat.id)
        linked = getattr(channel, "linked_chat_id", None)
        if not linked:
            return
        # In a linked discussion group, the channel post is represented by a
        # discussion message with the same message id. Replying there creates
        # the public comment without pretending the bot can post inside the
        # channel as a fake user.
        await context.bot.send_message(
            chat_id=linked,
            text=comment,
            reply_parameters={"message_id": post.message_id},
        )
    except Exception:
        # Channel comments are an enhancement; never take the bot down if a
        # channel has no discussion group or Telegram rejects the reply.
        return


HELP = """<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐑𝐀𝐂𝐋𝐄 · 𝐕𝟐</b>

<i>Not a command dump. Pick a door.</i>

<b>💞 SOCIAL</b>
/hug · /kiss · /pat · /kick · /slap · /punch
/highfive · /cuddle · /poke · /bonk · /bite
/wave · /wink · /dance · /roast
/bond · /oraclepair · /vow

<b>🏏 CRICKET</b>
/cricket — solo skill match
/cricketduel — multiplayer duel

<b>🎧 MIDNIGHT RADIO</b>
/midnightplay <i>song</i> — VC music

<b>🧬 IDENTITY</b>
/mprofile · /identity · /achievements
/aura · /vibecheck · /shadow · /element

<b>🌑 WORLD</b>
/midnightevent · /nightreport · /ritual · /sigil

<b>🌙 ORACLE</b>
/triggerinfo — current trigger
/settrigger <i>word</i> — admin only

<b>🛠️ HELP</b>
/upgradhelp — V2 upgrade guide

<i>Hinglish mode: ON. Ab bot boring nahi hoga. 🫠</i>"""


async def help_v2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def triggerinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pulse = await storage.load(_pulse_key(update.effective_chat.id), {})
    trigger = (pulse.get("trigger") if isinstance(pulse, dict) else None) or os.getenv("MIDNIGHT_TRIGGER", "midnight")
    await update.effective_message.reply_text(f"🌙 Current Midnight trigger: <code>{html.escape(str(trigger))}</code>", parse_mode=ParseMode.HTML)


def install(application) -> None:
    # Interaction commands intentionally live in a very early handler group so
    # the old compatibility command surface cannot steal them.
    application.add_handler(CommandHandler(list(ALIASES), interaction), group=-20)
    application.add_handler(CommandHandler(["help"], help_v2), group=-20)
    application.add_handler(CommandHandler(["settrigger"], settrigger), group=-20)
    application.add_handler(CommandHandler(["triggerinfo"], triggerinfo), group=-20)
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post), group=-20)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, observe), group=-19)
    application.add_handler(MessageHandler(filters.CAPTION & ~filters.COMMAND, observe), group=-19)
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post), group=-20)
    application.bot_data["midnight_v2_social"] = True
