"""Explicit /voice command for Midnight Oracle voice notes."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..voice_engine import VoiceEngine


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate one explicit, rate-limited Gemini voice note."""
    message = update.effective_message
    if not message or not update.effective_chat or not update.effective_user:
        return

    text = " ".join(context.args).strip()
    if not text:
        await message.reply_text("☾ Give me a line after /voice and I’ll say it.", reply_to_message_id=message.message_id)
        return

    application = context.application
    router = application.bot_data.get("oracle_router")
    engine = getattr(router, "voice", None) if router is not None else None
    if not isinstance(engine, VoiceEngine):
        engine = application.bot_data.get("oracle_voice_engine")
        if not isinstance(engine, VoiceEngine):
            engine = VoiceEngine()
            application.bot_data["oracle_voice_engine"] = engine

    decision = engine.decide(
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        text=text,
        direct=True,
        private=update.effective_chat.type == "private",
        explicit=True,
    )
    if not decision.should_send:
        await message.reply_text("☾ Voice is taking a little pause. Try again later.", reply_to_message_id=message.message_id)
        return

    audio = await engine.synthesize(text)
    if audio is None:
        await message.reply_text("☾ I couldn't shape that into a voice note this time. Try again.", reply_to_message_id=message.message_id)
        return

    try:
        await message.reply_voice(voice=audio, caption="☾ Midnight", reply_to_message_id=message.message_id)
        engine.record(update.effective_chat.id, update.effective_user.id, text)
    finally:
        audio.close()
