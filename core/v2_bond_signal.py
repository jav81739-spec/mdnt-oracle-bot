"""Midnight-native Bond and Signal layer.

Bond can choose a pairing automatically from recently observed group members;
Signal separates supported facts from interpretation/noise without exposing any
internal development lore or private data.
"""
from __future__ import annotations

import random
import re
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from .storage import storage


def _mention(user_id: int, name: str) -> str:
    safe = re.sub(r"[<>]", "", name or "Midnight Soul")[:80]
    return f'<a href="tg://user?id={int(user_id)}">{safe}</a>'


async def _recent_members(chat_id: int):
    """Use the existing lightweight V2 roster; never enumerate hidden members."""
    sources = [f"v2:pulse:{chat_id}", f"v2:auto:{chat_id}", f"midnight:roster:{chat_id}"]
    merged: dict[int, dict] = {}
    cutoff = time.time() - 7 * 86400
    for key in sources:
        raw = await storage.load(key, {})
        if not isinstance(raw, dict):
            continue
        members = raw.get("members", raw) if isinstance(raw.get("members", raw), dict) else {}
        for uid, item in members.items():
            if not isinstance(item, dict):
                continue
            try:
                user_id = int(item.get("user_id", uid))
                seen = float(item.get("seen", 0))
            except (TypeError, ValueError):
                continue
            if seen >= cutoff:
                merged[user_id] = {"user_id": user_id, "name": item.get("name") or "Midnight Soul", "seen": seen}
    return list(merged.values())


async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run a playful pairing without requiring the user to nominate a target."""
    chat = update.effective_chat
    me = update.effective_user
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("☾ Bond is a group ritual. Bring Midnight into a group and let it choose.")
        return

    members = [m for m in await _recent_members(chat.id) if int(m["user_id"]) != int(me.id)]
    if len(members) < 2:
        await update.effective_message.reply_text("☾ I need at least two recently observed members before I can choose a bond.")
        return

    a, b = random.sample(members, 2)
    score = random.randint(41, 99)
    titles = [
        ("✦ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐁𝐎𝐍𝐃 ✦", "Two paths crossed under the same night."),
        ("☾ 𝐐𝐔𝐈𝐄𝐓 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 ☽", "Interesting chemistry. Midnight is only measuring the vibe."),
        ("𖤓 𝐍𝐈𝐆𝐇𝐓 𝐏𝐀𝐈𝐑𝐈𝐍𝐆 𖤓", "No nominations. The Oracle picked this one."),
    ]
    title, line = random.choice(titles)
    await update.effective_message.reply_text(
        f"<b>{title}</b>\n\n{_mention(a['user_id'], a['name'])} × {_mention(b['user_id'], b['name'])}\n\n"
        f"<i>{line}</i>\n\n<b>𝐁𝐎𝐍𝐃 𝐒𝐘𝐍𝐂</b> · <b>{score}%</b>\n\n"
        "<i>For fun only. A score is fictional and says nothing about either person's real feelings.</i> 🌙",
        parse_mode=ParseMode.HTML,
    )


def _signal_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        return "☾ <b>SIGNAL</b>\n\nReply to a message or use <code>/signal your text</code> so Midnight can separate signal from noise."
    lower = text.lower()
    markers = []
    if any(x in lower for x in ("official", "confirmed", "announcement", "statement", "source", "reported")):
        markers.append("there is a claim of external confirmation")
    if "?" in text:
        markers.append("the message contains an open question")
    if any(x in lower for x in ("i think", "maybe", "probably", "feels like", "lagta hai", "shayad", "mujhe lagta")):
        markers.append("the wording signals interpretation rather than a verified fact")
    if any(x in lower for x in ("always", "never", "everyone", "nobody", "definitely", "100%")):
        markers.append("absolute wording increases the chance of overstatement")
    if markers:
        status = "🟡 <b>MIXED SIGNAL</b>"
        reason = "; ".join(markers[:2]) + "."
    else:
        status = "🟢 <b>CLEAR SIGNAL</b>"
        reason = "Nothing in the wording alone establishes a hidden fact; treat it as what it explicitly says."
    return f"☾ <b>SIGNAL CHECK</b>\n\n{status}\n\n<i>{reason}</i>\n\n<b>Rule:</b> facts first, interpretation second. Midnight won't invent the missing context. 🌙"


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    text = " ".join(context.args).strip() if context.args else ""
    if not text and message and message.reply_to_message:
        replied = message.reply_to_message
        text = replied.text or replied.caption or ""
    await message.reply_text(_signal_text(text), parse_mode=ParseMode.HTML)


def install(application):
    # Negative group runs before legacy command handlers, making these the single
    # authoritative implementations without deleting unrelated V1 functionality.
    application.add_handler(CommandHandler("bond", bond), group=-90)
    application.add_handler(CommandHandler("signal", signal), group=-90)
