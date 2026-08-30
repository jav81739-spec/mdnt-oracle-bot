"""Small, opt-in surprise layer for Midnight Oracle.

Surprises are manually triggered, rate-limited per user, and fail independently
from the rest of the bot. They never expose scheduler internals or private data.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

_COOLDOWN = 45.0
_LAST: dict[tuple[int, str], float] = {}

_MOMENTS = (
    ("🌙", "The Oracle opens a drawer that wasn't there a moment ago.\n\nInside: a tiny note — *keep going.*"),
    ("✦", "A strange signal crosses the archive.\n\n`something good is quietly becoming possible.`"),
    ("🕯️", "Midnight Oracle leaves one candle burning for you.\n\nNo prophecy. No task. Just a little light."),
    ("🪐", "The stars disagree with the archive tonight.\n\nOracle's verdict: *let the unexpected happen.*"),
    ("🎁", "A sealed midnight parcel has appeared.\n\nYou weren't supposed to find it this early. 😶‍🌫️"),
    ("🪞", "The mirror shows your reflection… then gives a tiny approving nod.\n\nOracle says nothing."),
    ("🍀", "A quiet lucky sign has been filed under your name.\n\nNo explanation. That's the point."),
    ("🪽", "A soft page turns in the dark.\n\nSome victories don't announce themselves."),
)

_EXTRA = (
    "You found the hidden door.",
    "The archive remembers this little moment.",
    "Tonight, curiosity wins.",
    "Keep this one. It may make sense later.",
)


def _allowed(user_id: int, command: str) -> bool:
    key = (user_id, command)
    now = time.monotonic()
    if now - _LAST.get(key, 0.0) < _COOLDOWN:
        return False
    _LAST[key] = now
    return True


def _pick(user_id: int, salt: str) -> tuple[str, str]:
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{user_id}:{stamp}:{salt}".encode()).digest()
    index = digest[0] % len(_MOMENTS)
    return _MOMENTS[index]


async def mysterybox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not _allowed(user.id, "mysterybox"):
        return
    icon, moment = _pick(user.id, "box")
    extra = _EXTRA[hashlib.sha256(f"{user.id}:{datetime.now(ZoneInfo('Asia/Kolkata')).date()}".encode()).digest()[1] % len(_EXTRA)]
    await update.effective_message.reply_text(f"{icon}  **MIDNIGHT MYSTERY**\n\n{moment}\n\n_{extra}_", parse_mode="Markdown")


async def muse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not _allowed(user.id, "muse"):
        return
    _, moment = _pick(user.id, "muse")
    await update.effective_message.reply_text(f"✦ **MUSE**\n\n{moment}\n\n_One small spark. That's all._", parse_mode="Markdown")


async def glitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not _allowed(user.id, "glitch"):
        return
    digest = hashlib.sha256(f"{user.id}:{datetime.now(ZoneInfo('Asia/Kolkata')).date()}:glitch".encode()).hexdigest()
    await update.effective_message.reply_text(
        "⚠️ **ARCHIVE GLITCH**\n\n"
        f"signal: `{digest[:8]}`\n"
        "status: _harmless_\n\n"
        "The Oracle refuses to explain what you just saw. 🌙",
        parse_mode="Markdown",
    )


async def nightgift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not _allowed(user.id, "nightgift"):
        return
    icon, moment = _pick(user.id, "gift")
    await update.effective_message.reply_text(f"{icon} **A LITTLE GIFT**\n\n{moment}\n\n_Keep the good vibe._", parse_mode="Markdown")


def register(app):
    app.add_handler(CommandHandler("mysterybox", mysterybox))
    app.add_handler(CommandHandler("muse", muse))
    app.add_handler(CommandHandler("glitch", glitch))
    app.add_handler(CommandHandler("nightgift", nightgift))
