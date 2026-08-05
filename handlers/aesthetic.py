import random
from telegram import Update
from telegram.ext import ContextTypes

ORACLE_LINES = [
    "The answer lies where you least expect it...",
    "Not yet. But soon, the fog will clear.",
    "What you seek is already seeking you.",
    "Silence holds the truth you're avoiding.",
]

TAROT_CARDS = [
    ("The Fool 🃏", "New beginnings await — leap without fear."),
    ("The Moon 🌙", "Nothing is quite as it seems tonight."),
    ("The Star ⭐", "Hope returns after the storm."),
    ("The Tower 🗼", "Something is about to break — and that's okay."),
]

AURA_COLORS = [
    ("Violet 💜", "mysterious and deep — you see what others miss"),
    ("Crimson ❤️‍🔥", "intense energy — you burn bright in every room"),
    ("Silver 🩶", "calm and unreadable — a quiet storm"),
    ("Gold 💛", "magnetic — people are drawn to you without knowing why"),
]


async def oracle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args) if context.args else "your question"
    await update.message.reply_text(f"🔮 *The Oracle speaks on \"{question}\":*\n\n_{random.choice(ORACLE_LINES)}_", parse_mode="Markdown")


async def tarot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card, meaning = random.choice(TAROT_CARDS)
    await update.message.reply_text(f"🃏 You drew: *{card}*\n\n_{meaning}_", parse_mode="Markdown")


async def aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    color, vibe = random.choice(AURA_COLORS)
    await update.message.reply_text(f"✨ {target.first_name}'s aura is *{color}*\n_{vibe}_", parse_mode="Markdown")


async def confess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anonymous confession — bot posts it, identity is not shown in the group."""
    if not context.args:
        await update.message.reply_text("Usage: /confess your secret text")
        return
    confession_text = " ".join(context.args)
    try:
        await update.message.delete()  # remove the original so identity isn't in chat history
    except Exception:
        pass
    await context.bot.send_message(
        update.effective_chat.id,
        f"🕯️ *Anonymous confession:*\n\n{confession_text}",
        parse_mode="Markdown",
    )
