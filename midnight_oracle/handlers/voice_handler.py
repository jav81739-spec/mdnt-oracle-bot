"""Explicit /voice command for Midnight Oracle voice notes."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..voice_engine import VoiceEngine


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Speak supplied text; generation failures fall back to a normal reply."""
    message = update.effective_message
    if not message:
        return
    text = " ".join(context.args).strip()
    if not text:
        await message.reply_text("☾ Give me a line after /voice and I’ll say it.")
        return
    engine = VoiceEngine()
    if not engine.client:
        await message.reply_text("☾ Voice is resting right now. Text mode is still here.")
        return
    audio = await engine.synthesize(text)
    if audio is None:
        await message.reply_text("☾ I couldn't shape that into a voice note this time. Try again.")
        return
    try:
        await message.reply_voice(voice=audio, caption="☾ Midnight")
    finally:
        audio.close()
