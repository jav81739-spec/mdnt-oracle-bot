"""Midnight-native Bond and Signal layer."""
from __future__ import annotations

import html
import random
import re
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationHandlerStop, CommandHandler, ContextTypes

from .storage import storage


def _mention(user_id: int, name: str) -> str:
    safe = html.escape(name or "Midnight Soul")[:80]
    return f'<a href="tg://user?id={int(user_id)}">{safe}</a>'


async def _recent_members(chat_id: int):
    """Merge every lightweight activity roster used by Midnight."""
    sources = [f"v2:pulse:{chat_id}", f"v2:auto:{chat_id}", f"midnight:roster:{chat_id}"]
    merged: dict[int, dict] = {}
    cutoff = time.time() - 10 * 86400
    for key in sources:
        try:
            raw = await storage.load(key, {})
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        members = raw.get("members", raw)
        if not isinstance(members, dict):
            continue
        for uid, item in members.items():
            if not isinstance(item, dict):
                continue
            try:
                user_id = int(item.get("user_id", uid))
                seen = float(item.get("seen", 0))
            except (TypeError, ValueError):
                continue
            if seen >= cutoff:
                merged[user_id] = {"user_id": user_id, "name": str(item.get("name") or "Midnight Soul"), "seen": seen}
    return list(merged.values())


async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    me = update.effective_user
    message = update.effective_message
    if not chat or chat.type == "private" or not me or not message:
        await message.reply_text("☾ Bond is a group ritual. Bring Midnight into a group and let it choose.")
        return

    members = await _recent_members(chat.id)
    if not any(int(m["user_id"]) == int(me.id) for m in members):
        members.append({"user_id": int(me.id), "name": me.first_name or "Midnight Soul", "seen": time.time()})
    if len(members) < 2:
        await message.reply_text("☾ I need at least two observed people before I can choose a bond. Talk in the group once, then try again.")
        return

    pool = [m for m in members if int(m["user_id"]) != int(me.id)]
    if not pool:
        pool = members
    first = random.choice(pool)
    remaining = [m for m in members if int(m["user_id"]) != int(first["user_id"])]
    second = random.choice(remaining)
    score = random.randint(41, 99)
    titles = [
        ("✦ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐁𝐎𝐍𝐃 ✦", "Two paths crossed under the same night."),
        ("☾ 𝐐𝐔𝐈𝐄𝐓 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 ☽", "Interesting chemistry. Midnight is only measuring the vibe."),
        ("𖤓 𝐍𝐈𝐆𝐇𝐓 𝐏𝐀𝐈𝐑𝐈𝐍𝐆 𖤓", "No nominations. The Oracle picked this one."),
    ]
    title, line = random.choice(titles)
    await message.reply_text(
        f"<b>{title}</b>\n\n{_mention(first['user_id'], first['name'])} × {_mention(second['user_id'], second['name'])}\n\n"
        f"<i>{line}</i>\n\n<b>𝐁𝐎𝐍𝐃 𝐒𝐘𝐍𝐂</b> · <b>{score}%</b>\n\n"
        "<i>For fun only. The score is fictional and says nothing about real feelings.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


def _signal_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        return "☾ <b>SIGNAL</b>\n\nReply to a message or use <code>/signal your text</code>. Midnight will separate explicit signal from interpretation."
    lower = text.lower()
    markers = []
    if any(x in lower for x in ("official", "confirmed", "announcement", "statement", "source", "reported")):
        markers.append("there is wording that claims external confirmation")
    if "?" in text:
        markers.append("the message contains an open question")
    if any(x in lower for x in ("i think", "maybe", "probably", "feels like", "lagta hai", "shayad", "mujhe lagta")):
        markers.append("the wording signals interpretation rather than a verified fact")
    if any(x in lower for x in ("always", "never", "everyone", "nobody", "definitely", "100%")):
        markers.append("absolute wording increases the chance of overstatement")
    status = "🟡 <b>MIXED SIGNAL</b>" if markers else "🟢 <b>CLEAR SIGNAL</b>"
    reason = "; ".join(markers[:2]) + "." if markers else "Nothing in the wording alone establishes a hidden fact; treat it as what it explicitly says."
    return f"☾ <b>SIGNAL CHECK</b>\n\n{status}\n\n<i>{html.escape(reason)}</i>\n\n<b>Rule:</b> facts first, interpretation second. Midnight won't invent missing context. 🌙"


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    text = " ".join(context.args).strip() if context.args else ""
    if not text and message and message.reply_to_message:
        replied = message.reply_to_message
        text = replied.text or replied.caption or ""
        if not text and replied.sticker:
            text = "[sticker]"
        elif not text and replied.animation:
            text = "[animation]"
        elif not text and replied.photo:
            text = "[photo]"
    await message.reply_text(_signal_text(text), parse_mode=ParseMode.HTML)


async def _bond_once(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await bond(update, context)
    raise ApplicationHandlerStop


async def _signal_once(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal(update, context)
    raise ApplicationHandlerStop


def install(application):
    # These commands also exist in the compatibility runtime. Stop processing
    # the same update after V2 handles them, otherwise Telegram receives two
    # replies (V2 + legacy handler in a later handler group).
    application.add_handler(CommandHandler(["bond", "oraclepair"], _bond_once), group=-90)
    application.add_handler(CommandHandler(["signal", "signalcheck"], _signal_once), group=-90)
