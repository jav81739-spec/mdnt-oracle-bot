"""User-invoked autonomous commands; intentionally independent of scheduler jobs."""
from __future__ import annotations
import html
from telegram.ext import CommandHandler
from .storage import storage

KEY_PREFIX = "v2:autonomous:trigger:"


def _reply(message, text):
    return message.reply_text(text, reply_to_message_id=message.message_id)

async def settrigger(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in ("group", "supergroup"):
        await _reply(message, "☾ /settrigger belongs in a group.")
        return
    try:
        member = await chat.get_member(user.id)
        if member.status not in ("administrator", "creator"):
            await _reply(message, "🌘 Sirf group admins trigger set kar sakte hain.")
            return
    except Exception:
        await _reply(message, "🌘 I couldn't verify your admin status.")
        return
    word = " ".join(context.args).strip().casefold() if context.args else ""
    if len(word.split()) != 1 or not word.isalnum() or len(word) > 32:
        await _reply(message, "☾ Usage: /settrigger <one-word>")
        return
    ok = await storage.set(KEY_PREFIX + str(chat.id), word, ttl=8 * 24 * 3600)
    if not ok:
        await _reply(message, "🌘 I couldn't save that trigger right now.")
        return
    await _reply(message, f"✦ Trigger set to <code>{html.escape(word)}</code>.\n\nAb ye word bolo… Midnight pop out karega. 🌙")

async def triggerinfo(update, context):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    value = await storage.load(KEY_PREFIX + str(chat.id), None)
    if not isinstance(value, str) or not value:
        value = "midnight"
    await _reply(message, f"🌙 Current trigger: <code>{html.escape(value)}</code>")

def register(app):
    existing = {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}
    for name, callback in (("settrigger", settrigger), ("triggerinfo", triggerinfo)):
        if name not in existing:
            app.add_handler(CommandHandler(name, callback), group=16)
            existing.add(name)
