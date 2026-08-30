"""Rare, member-triggered Midnight Oracle surprise experiences."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler


def _seed(update: Update, salt: str = "") -> int:
    user = update.effective_user
    chat = update.effective_chat
    day = datetime.now(timezone.utc).date().isoformat()
    raw = f"{getattr(user, 'id', 0)}:{getattr(chat, 'id', 0)}:{day}:{salt}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:12], 16)


async def mysterybox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    choices = (
        "🗝️ *MIDNIGHT BOX — OPENED*\n\nYou found a sealed note:\n_‘Not every quiet moment is empty.’_\n\n✦ Keep this one.",
        "🎁 *MIDNIGHT BOX — UNCOMMON*\n\nA tiny archive token appeared:\n`THE NIGHT REMEMBERS`\n\n🌙 Some doors are better discovered than announced.",
        "🪞 *MIDNIGHT BOX — STRANGE*\n\nThe Oracle found a reflection that wasn't there a second ago.\n\n_It says: ‘Look again tomorrow.’_",
        "🌌 *MIDNIGHT BOX — RARE*\n\nTonight's little discovery:\n**You were here. That counts.**\n\n✦ Archive entry saved in spirit.",
    )
    await update.effective_message.reply_text(choices[_seed(update, 'box') % len(choices)], parse_mode='Markdown')


async def nightgift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    gifts = (
        "🌙 *NIGHT GIFT*\nA pocket-sized piece of calm: _take one breath before the next thing._",
        "🕯️ *NIGHT GIFT*\nThe Oracle leaves the light on for one more conversation.",
        "✦ *NIGHT GIFT*\nA free pass to do absolutely nothing for sixty seconds. No guilt attached.",
        "💌 *NIGHT GIFT*\nA reminder from the archives: _you don't have to finish everything tonight._",
    )
    await update.effective_message.reply_text(gifts[_seed(update, 'gift') % len(gifts)], parse_mode='Markdown')


async def muse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sparks = (
        '✦ Make something tiny that only you understand.',
        '🌙 Write the first sentence. Let tomorrow write the second.',
        '🪶 Turn one ordinary moment into a story before the day forgets it.',
        '🧩 Ask a better question instead of forcing an easy answer.',
        '🌌 Keep one idea private until it becomes impossible to ignore.',
    )
    await update.effective_message.reply_text(f"*ORACLE MUSE*\n\n{sparks[_seed(update, 'muse') % len(sparks)]}", parse_mode='Markdown')


async def glitch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    glitches = (
        "🪞 *ARCHIVE GLITCH*\n\nSignal stable. Reality slightly questionable.\n\n`echo: you are still here`",
        "⚠️ *ARCHIVE GLITCH*\n\nOne midnight frame arrived out of order.\n\n`frame[-1] → frame[0] → ✦`",
        "👁️ *ARCHIVE GLITCH*\n\nThe Oracle looked back before you looked forward.\n\nNo damage detected. Probably.",
    )
    await update.effective_message.reply_text(glitches[_seed(update, 'glitch') % len(glitches)], parse_mode='Markdown')


def register(app) -> None:
    app.add_handler(CommandHandler('mysterybox', mysterybox))
    app.add_handler(CommandHandler('nightgift', nightgift))
    app.add_handler(CommandHandler('muse', muse))
    app.add_handler(CommandHandler('glitch', glitch))
