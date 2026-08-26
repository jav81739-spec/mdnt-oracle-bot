"""Polished Midnight V2 social layer.

Includes a large original interaction vocabulary, visual text cards, Hinglish
triggering, observed-member group pulse and relevant linked-channel comments.
"""
from __future__ import annotations

import html
import os
import random
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from .storage import storage

ACTIONS = {
    "hug": ("🫂", "HUG", ["idhar aa, ek proper hug banta hai.", "warm sa Midnight hug delivered."]),
    "kiss": ("💋", "KISS", ["mwah — bas itna hi allowed tonight.", "Oracle-approved kiss. 😌"]),
    "pat": ("🫳", "PAT", ["pat pat. ab drama thoda kam.", "head pat delivered with suspicious sincerity."]),
    "kick": ("🦶", "KICK", ["one dramatic kick — purely fictional.", "bonk—wrong universe, same energy. 😭"]),
    "slap": ("🫲", "SLAP", ["cartoon-level slap. zero real damage.", "*thappad.exe* — group-game mode only."]),
    "punch": ("👊", "PUNCH", ["POW! straight out of a comic panel.", "one harmless dramatic punch. 💥"]),
    "highfive": ("🙌", "HIGH FIVE", ["clean high-five. ✋", "team energy +1."]),
    "cuddle": ("🧸", "CUDDLE", ["soft corner unlocked.", "Midnight has temporarily banned loneliness."]),
    "poke": ("👉", "POKE", ["poke.", "POKE POKE. now you have to react. 👀"]),
    "bonk": ("🔨", "BONK", ["bonk. respectfully.", "BONK — go drink water. 😭"]),
    "bite": ("🦷", "BITE", ["tiny fictional bite. no hospital required. 😭", "nom. blame the Oracle."]),
    "wave": ("👋", "WAVE", ["a moonlit wave from Midnight.", "wave received and returned. 🌙"]),
    "wink": ("😉", "WINK", ["one suspicious wink.", "Oracle saw that. 👀"]),
    "dance": ("🕺", "DANCE", ["music on. dignity off.", "one completely unnecessary dance break."]),
    "roast": ("🔥", "ROAST", ["light roast only. Midnight has standards.", "tiny roast, perfectly toasted."]),
    "cheer": ("📣", "CHEER", ["the Oracle is now your personal hype section.", "confidence restored. 👏"]),
    "comfort": ("🌙", "COMFORT", ["no fixing, just company.", "soft mode enabled. 🫂"]),
    "tickle": ("🪶", "TICKLE", ["harmless tickle attack. 😭", "you have been ambushed by feathers."]),
    "salute": ("🫡", "SALUTE", ["Midnight acknowledges the legend.", "formal salute. very serious business."]),
    "stare": ("👁️", "STARE", ["the Oracle is staring back.", "👁️ ... 👁️"]),
    "handshake": ("🤝", "HANDSHAKE", ["deal sealed.", "respect exchanged. 🤝"]),
    "fistbump": ("👊", "FIST BUMP", ["clean fist bump.", "bro-code successfully transmitted."]),
    "shoulderpat": ("🫱", "SHOULDER PAT", ["you got this.", "quiet support, Midnight style."]),
    "highfive": ("🙌", "HIGH FIVE", ["clean high-five. ✋", "that one echoed through the timeline."]),
    "cheers": ("🥂", "CHEERS", ["to another questionable decision. 🌙", "cheers, legend. 🥂"]),
}
ALIASES = {k: k for k in ACTIONS}
ALIASES.update({"high5": "highfive", "hi5": "highfive", "fist": "fistbump", "shoulder": "shoulderpat"})


def mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{html.escape(user.first_name or "Midnight Soul")}</a>'


def target(update: Update):
    reply = update.effective_message.reply_to_message if update.effective_message else None
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return None


async def interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.effective_message.text or "").split()[0].split("@")[0].lstrip("/").lower()
    action = ALIASES.get(raw)
    if not action:
        return
    who = target(update)
    if not who:
        await update.effective_message.reply_text(
            f"☾ <b>{ACTIONS[action][1]} RITUAL</b>\n\nReply to someone's message and use /{raw}.\n\n<i>kya scene hai? Midnight sun raha hai. 🌙</i>",
            parse_mode=ParseMode.HTML,
        )
        return
    if who.id == update.effective_user.id:
        await update.effective_message.reply_text("🌘 khud ko target karke Oracle ko confuse mat karo 😭", parse_mode=ParseMode.HTML)
        return
    emoji, title, lines = ACTIONS[action]
    card = (
        "<b>━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>{emoji} 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 · {title}</b>\n\n"
        f"{mention(update.effective_user)}  →  {mention(who)}\n\n"
        f"<i>{random.choice(lines)}</i>\n\n"
        "<code>☾ visual interaction · just for fun</code>\n"
        "<b>━━━━━━━━━━━━━━━━━━</b>"
    )
    await update.effective_message.reply_text(card, parse_mode=ParseMode.HTML)


async def observe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot:
        return
    now = time.time()
    key = f"v2:pulse:{chat.id}"
    pulse = await storage.load(key, {})
    if not isinstance(pulse, dict):
        pulse = {}
    previous = float(pulse.get("last_message", now))
    pulse["last_message"] = now
    pulse["messages"] = int(pulse.get("messages", 0)) + 1
    members = pulse.get("members", {})
    if not isinstance(members, dict):
        members = {}
    members[str(user.id)] = {"name": user.first_name or "Midnight Soul", "seen": now}
    pulse["members"] = members
    await storage.set(key, pulse, ttl=8 * 24 * 3600)

    text = (update.effective_message.text or update.effective_message.caption or "").lower()
    trigger = str(pulse.get("trigger") or os.getenv("MIDNIGHT_TRIGGER", "midnight")).lower().strip()
    words = {w.strip(".,!?;:()[]{}<>\"'`") for w in text.split()}
    if trigger and trigger in words and now - float(pulse.get("last_trigger", 0)) >= 20:
        pulse["last_trigger"] = now
        await storage.set(key, pulse, ttl=8 * 24 * 3600)
        await update.effective_message.reply_text(random.choice([
            "☾ <b>𝐘𝐎𝐔 𝐂𝐀𝐋𝐋𝐄𝐃?</b>\n\nHaan bhai, Midnight sun raha hai. Kya scene hai? 👀",
            "🌙 <b>𝐎𝐑𝐀𝐂𝐋𝐄 𝐀𝐖𝐀𝐊𝐄</b>\n\nBol diya naam… ab chaos bhi tumhara. 🫠",
            "🌘 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐍𝐋𝐈𝐍𝐄</b>\n\nAcha… kisne mujhe yaad kiya? 👁️",
        ]), parse_mode=ParseMode.HTML)
        return

    quiet_for = now - previous
    if quiet_for >= 45 * 60 and now - float(pulse.get("last_awakened", 0)) >= 6 * 3600:
        pulse["last_awakened"] = now
        await storage.set(key, pulse, ttl=8 * 24 * 3600)
        if quiet_for >= 3 * 3600:
            message = "🌘 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐄𝐒𝐔𝐑𝐑𝐄𝐂𝐓𝐈𝐎𝐍</b>\n\nGroup itna shaant? 😭\n\n<b>First person to answer:</b> Who wins tonight's cricket debate? 🏏"
        else:
            message = "☾ <b>𝐐𝐔𝐈𝐄𝐓 𝐇𝐎𝐔𝐑</b>\n\nSab chup kyun hain? 😭\n\n<b>Pick one:</b> 🏏 cricket · 🎧 song · 🎮 game"
        await update.effective_message.reply_text(message, parse_mode=ParseMode.HTML)


async def settrigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await update.effective_chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        await update.effective_message.reply_text("🌘 Sirf admins trigger set kar sakte hain.")
        return
    word = " ".join(context.args).strip().lower()
    if not word or len(word.split()) != 1 or len(word) > 32:
        await update.effective_message.reply_text("☾ Usage: /settrigger <one-word>")
        return
    key = f"v2:pulse:{update.effective_chat.id}"
    pulse = await storage.load(key, {})
    if not isinstance(pulse, dict): pulse = {}
    pulse["trigger"] = word
    await storage.set(key, pulse, ttl=8 * 24 * 3600)
    await update.effective_message.reply_text(f"✦ Trigger set to <code>{html.escape(word)}</code>.\n\nAb ye word bolo… Midnight pop out karega. 🌙", parse_mode=ParseMode.HTML)


async def triggerinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pulse = await storage.load(f"v2:pulse:{update.effective_chat.id}", {})
    word = pulse.get("trigger") if isinstance(pulse, dict) else None
    word = word or os.getenv("MIDNIGHT_TRIGGER", "midnight")
    await update.effective_message.reply_text(f"🌙 Trigger: <code>{html.escape(str(word))}</code>", parse_mode=ParseMode.HTML)


CHANNELS = tuple(int(x.strip()) for x in os.getenv("MIDNIGHT_ASSOCIATED_CHANNELS", "").split(",") if x.strip().lstrip("-").isdigit())


def relevant_comment(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ("cricket", "ipl", "odi", "t20", "test", "wicket", "runs", "match")):
        return random.choice(["🏏 Ye update toh seedha boundary hai. 👀", "Cricket scene spotted — group mein discussion pakka. 🏏🌙", "Oho, cricket timeline phir interesting ho gayi. 👁️🏏"])
    if any(x in t for x in ("win", "won", "champion", "trophy", "victory")):
        return random.choice(["🏆 Victory energy detected. Midnight approves. 👑", "Acha ji, celebration banti hai. 🔥", "Big moment. Isko archive mein rakho. 🌙"])
    if any(x in t for x in ("breaking", "official", "confirmed", "announcement")):
        return random.choice(["👀 Okay, this one matters. Midnight has seen it.", "Confirmed? Ab scene serious hai. 🌙", "Breaking energy detected. 👁️"])
    return random.choice(["🌙 Ye post quietly deserved a Midnight reaction. 👀", "Acha post hai — Midnight ne notice kar liya. ✦", "Timeline pe ye wala moment rukne layak tha. 🌙"])


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post or post.chat.id not in CHANNELS:
        return
    try:
        channel = await context.bot.get_chat(post.chat.id)
        linked = getattr(channel, "linked_chat_id", None)
        if not linked:
            return
        await context.bot.send_message(
            chat_id=linked,
            text=relevant_comment(post.text or post.caption or ""),
            reply_parameters={"message_id": post.message_id},
        )
    except Exception:
        return


HELP = """<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐑𝐀𝐂𝐋𝐄 · 𝐕𝟐</b>

<i>Hinglish mode: ON. Pick a door.</i>

<b>💞 INTERACTIONS</b>
/hug /kiss /pat /kick /slap /punch
/highfive /cuddle /poke /bonk /bite /wave
/wink /dance /roast /cheer /comfort
/tickle /salute /stare /handshake /fistbump
/shoulderpat /cheers

<b>🌙 ORACLE</b>
/bond /oraclepair /vow
/settrigger <i>word</i> · /triggerinfo

<b>🏏 CRICKET</b>
/cricket · /cricketduel

<b>🎧 VC RADIO</b>
/midnightplay <i>song</i>

<b>🧬 IDENTITY + WORLD</b>
/mprofile /identity /achievements
/aura /vibecheck /shadow /element
/midnightevent /nightreport /ritual /sigil

<b>🛠️ UPGRADE</b>
/upgradhelp

<i>Midnight watches the room, remembers safe game state, and can wake a quiet group without being spammy.</i> 🌘"""


async def help_v2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def install(application):
    application.add_handler(CommandHandler(list(ALIASES), interaction), group=-30)
    application.add_handler(CommandHandler(["help"], help_v2), group=-30)
    application.add_handler(CommandHandler(["settrigger"], settrigger), group=-30)
    application.add_handler(CommandHandler(["triggerinfo"], triggerinfo), group=-30)
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post), group=-30)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, observe), group=-29)
    application.add_handler(MessageHandler(filters.CAPTION & ~filters.COMMAND, observe), group=-29)
