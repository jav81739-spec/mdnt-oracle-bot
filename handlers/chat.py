"""Human-style Telegram chat with durable settings and one AI gateway."""
from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core.ai import AIUnavailable
from core.chat import generate_reply as core_generate_reply
from handlers import storage

log = logging.getLogger("midnight.chat")

chat_enabled: dict[str, bool] = {}
chat_persona: dict[str, str] = {}
chat_history: dict[str, list[dict[str, str]]] = {}
_last_reply_time: dict[str, float] = {}

DEFAULT_PERSONA = "friendly, casual, playful, naturally Hinglish when appropriate"
MAX_HISTORY = 10
COOLDOWN_SECONDS = 3
STORAGE_KEY = "chat_settings"


async def load_from_storage() -> None:
    global chat_enabled, chat_persona
    saved = await storage.load(STORAGE_KEY, {"enabled": {}, "persona": {}})
    if not isinstance(saved, dict):
        saved = {}
    chat_enabled = dict(saved.get("enabled", {}))
    chat_persona = dict(saved.get("persona", {}))


async def _persist() -> None:
    if not await storage.save(STORAGE_KEY, {"enabled": chat_enabled, "persona": chat_persona}):
        raise RuntimeError("chat settings could not be persisted")


async def toggle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    async with storage.lock(f"chat-settings:{chat_id}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Chat settings are busy — try again.")
            return
        saved = await storage.load(STORAGE_KEY, {"enabled": {}, "persona": {}})
        enabled = dict(saved.get("enabled", {})) if isinstance(saved, dict) else {}
        personas = dict(saved.get("persona", {})) if isinstance(saved, dict) else {}
        enabled[chat_id] = not bool(enabled.get(chat_id, False))
        chat_enabled.update(enabled); chat_persona.update(personas)
        if not await storage.save(STORAGE_KEY, {"enabled": enabled, "persona": personas}):
            raise RuntimeError("chat settings could not be persisted")
        state = "ON ✅" if enabled[chat_id] else "OFF ❌"
    await update.message.reply_text(f"Chat mode is now {state}\n_(saved across restarts)_", parse_mode="Markdown")


async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    style = (" ".join(context.args).strip() if context.args else DEFAULT_PERSONA)[:300]
    async with storage.lock(f"chat-settings:{chat_id}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Chat settings are busy — try again.")
            return
        saved = await storage.load(STORAGE_KEY, {"enabled": {}, "persona": {}})
        enabled = dict(saved.get("enabled", {})) if isinstance(saved, dict) else {}
        personas = dict(saved.get("persona", {})) if isinstance(saved, dict) else {}
        personas[chat_id] = style
        chat_enabled.update(enabled); chat_persona.update(personas)
        if not await storage.save(STORAGE_KEY, {"enabled": enabled, "persona": personas}):
            raise RuntimeError("chat settings could not be persisted")
    await update.message.reply_text(f"Persona updated: {style}")


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not chat_enabled.get(chat_id, False) or not update.message or not update.message.text:
        return
    message = update.message
    bot_username = context.bot.username
    was_mentioned = bool(bot_username and f"@{bot_username}" in message.text)
    was_replied_to = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == context.bot.id)
    if not (was_mentioned or was_replied_to or "midnight" in message.text.lower()):
        return
    now = time.monotonic()
    if now - _last_reply_time.get(chat_id, 0.0) < COOLDOWN_SECONDS:
        return
    _last_reply_time[chat_id] = now
    persona = chat_persona.get(chat_id, DEFAULT_PERSONA)
    history = chat_history.setdefault(chat_id, [])
    history.append({"role": "user", "text": message.text[:1000]})
    del history[:-MAX_HISTORY]
    try:
        reply_text = await generate_reply(message.text, persona, history)
    except AIUnavailable as exc:
        log.info("AI unavailable for chat=%s: %s", chat_id, exc)
        await message.reply_text("🌙 my signal is a little weak right now — try again in a moment.")
        return
    except Exception:
        log.exception("Unexpected AI chat failure for chat=%s", chat_id)
        await message.reply_text("🌙 something tangled the signal — try that again.")
        return
    if not reply_text:
        await message.reply_text("🔌 AI chat needs a GEMINI_API_KEY in the deployment environment.")
        return
    history.append({"role": "assistant", "text": reply_text[:2000]})
    del history[:-MAX_HISTORY]
    await message.reply_text(reply_text)


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """Compatibility wrapper: all generation now goes through the core gateway."""
    if not ai_service_configured():
        return None
    return await core_generate_reply(user_text, persona, history)


def ai_service_configured() -> bool:
    """Avoid a network call when no Gemini secret exists."""
    from core.ai import service
    return bool(service.api_key)
