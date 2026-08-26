"""Midnight V2 autonomous room intelligence.

Conservative by design: observe activity, remember only lightweight room state,
and speak only after cooldowns. No unsolicited private messages.
"""
from __future__ import annotations

import random
import time
from telegram.ext import ContextTypes, MessageHandler, filters
from .storage import storage

COOLDOWN = 3 * 3600
QUIET = 90 * 60

async def pulse(update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot or not message:
        return
    now = time.time()
    key = f"v2:auto:{chat.id}"
    state = await storage.load(key, {})
    if not isinstance(state, dict): state = {}
    last = float(state.get("last", 0)); state["last"] = now
    members = state.get("members", {}) if isinstance(state.get("members", {}), dict) else {}
    members[str(user.id)] = {"name": user.first_name or "Soul", "seen": now}
    state["members"] = members
    text = (message.text or message.caption or "").lower()
    state["topics"] = {"cricket": int("cricket" in text or "ipl" in text or "wicket" in text), "music": int("song" in text or "music" in text), "night": int("night" in text or "good night" in text)}
    should_awaken = last and now - last >= QUIET and now - float(state.get("last_awaken", 0)) >= COOLDOWN
    if should_awaken:
        state["last_awaken"] = now
        await storage.set(key, state, ttl=10 * 24 * 3600)
        topic = max(state["topics"], key=state["topics"].get)
        prompts = {
            "cricket": "🏏 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐂𝐑𝐄𝐀𝐒𝐄</b>\n\nGroup phir cricket pe aa gaya. 👀\n\nSolo shot choose karoge ya kisi ko /cricketduel challenge karna hai?",
            "music": "🎧 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐀𝐃𝐈𝐎</b>\n\nSong talk detected. 👀\n\nKisi track ko VC mein le jaana ho toh /midnightplay try karo.",
            "night": "🌙 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐇𝐎𝐔𝐑</b>\n\nRaat ka scene officially active hai. 🫠",
        }
        await message.reply_text(prompts[topic], parse_mode="HTML")
    else:
        await storage.set(key, state, ttl=10 * 24 * 3600)

def install(application):
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, pulse), group=30)
    application.add_handler(MessageHandler(filters.CAPTION & ~filters.COMMAND, pulse), group=30)
