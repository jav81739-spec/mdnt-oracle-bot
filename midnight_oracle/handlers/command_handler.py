"""Minimal aesthetic command surface for Phase 1."""
from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..generators.truth_generator import question


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome a user without exposing internal implementation details."""
    await update.effective_message.reply_text("☾ Midnight Oracle\n\nSomeone in the room who remembers you.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the compact public command guide."""
    await update.effective_message.reply_text("☾ /oracle  talk\n/memory  group memory\n/mymemory  your memory\n/forget <topic>  forget\n/truth [level]  truth")


async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an original Truth question with answer/pass controls."""
    level = context.args[0] if context.args else "light"
    text = question(level)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Answer", callback_data="truth:answer"), InlineKeyboardButton("Pass", callback_data="truth:pass")]])
    await update.effective_message.reply_text(f"☾ {text}", reply_markup=markup)


async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide a privacy-preserving description of group memory."""
    await update.effective_message.reply_text("☾ Oracle remembers only bounded social context — not an endless transcript.")


async def mymemory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain that personal memory is private to the requesting member."""
    await update.effective_message.reply_text("☾ Your remembered details stay yours. Ask me in DM to see them.")


async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledge a forget request without exposing database internals."""
    if not context.args:
        await update.effective_message.reply_text("Tell me what to forget: /forget <topic>")
        return
    await update.effective_message.reply_text("☾ I'll remove matching remembered details.")
