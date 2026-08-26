"""Optional Midnight V2 voice-chat music player.

A Telegram bot account cannot itself join a voice chat as a normal media client.
When VC_API_ID/VC_API_HASH/VC_SESSION_STRING are configured, this module starts a
separate MTProto assistant in the same process and uses PyTgCalls. Without those
credentials, requests fail gracefully instead of breaking the bot.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from .storage import storage

DOWNLOAD_DIR = Path(os.getenv("MIDNIGHT_MUSIC_DIR", "/tmp/midnight-oracle-music"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_assistant = None
_calls = None
_start_lock = asyncio.Lock()
_started = False


def _configured() -> bool:
    return bool(os.getenv("VC_API_ID") and os.getenv("VC_API_HASH") and os.getenv("VC_SESSION_STRING"))

async def _ensure_player() -> bool:
    global _assistant, _calls, _started
    if _started:
        return True
    if not _configured():
        return False
    async with _start_lock:
        if _started:
            return True
        try:
            from pyrogram import Client
            from pytgcalls import PyTgCalls
            _assistant = Client(
                "midnight_oracle_vc",
                api_id=int(os.environ["VC_API_ID"]),
                api_hash=os.environ["VC_API_HASH"],
                session_string=os.environ["VC_SESSION_STRING"],
                in_memory=True,
            )
            await _assistant.start()
            _calls = PyTgCalls(_assistant)
            await _calls.start()
            _started = True
            return True
        except Exception:
            _assistant = None
            _calls = None
            return False


def _query_from(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = " ".join(context.args or []).strip()
    if query:
        return query
    reply = update.effective_message.reply_to_message if update.effective_message else None
    return (reply.text or reply.caption or "").strip() if reply else ""


def _safe_name(value: str) -> str:
    return re.sub(r"[^\w .()\[\]-]+", "", value)[:100].strip() or "midnight-track"

async def _resolve_song(query: str) -> dict[str, Any]:
    def work():
        import yt_dlp
        options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch1",
            "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(query, download=True)
            if "entries" in info:
                info = next(x for x in info["entries"] if x)
            base = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
            return {"title": info.get("title") or "Unknown track", "url": info.get("webpage_url") or query, "path": str(base)}
    return await asyncio.to_thread(work)

async def _play_next(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    queue = await storage.load(f"music:queue:{chat_id}", [])
    if not isinstance(queue, list) or not queue:
        return None
    item = queue.pop(0)
    await storage.set(f"music:queue:{chat_id}", queue, ttl=24 * 3600)
    if not await _ensure_player():
        return item
    try:
        from pytgcalls.types import MediaStream
        await _calls.play(chat_id, MediaStream(item["path"], video_flags=MediaStream.Flags.IGNORE))
        return item
    except Exception:
        return None

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _query_from(update, context)
    if not query:
        await update.effective_message.reply_text("🎧 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐏𝐋𝐀𝐘</b>\n\nGive me a song name — or reply to a message containing one.", parse_mode=ParseMode.HTML)
        return
    await update.effective_message.reply_text("☾ <i>Searching the night for that track…</i>", parse_mode=ParseMode.HTML)
    try:
        item = await _resolve_song(query)
    except Exception:
        await update.effective_message.reply_text("🌘 I couldn't fetch that track right now. Try the song title again.")
        return
    queue = await storage.load(f"music:queue:{update.effective_chat.id}", [])
    if not isinstance(queue, list):
        queue = []
    queue.append(item)
    await storage.set(f"music:queue:{update.effective_chat.id}", queue, ttl=24 * 3600)
    if not await _ensure_player():
        await update.effective_message.reply_text(
            f"<b>🎧 {item['title']}</b>\n\n<i>Fetched and queued, but the Midnight VC assistant is not configured yet.</i>\n\nSet <code>VC_API_ID</code>, <code>VC_API_HASH</code> and <code>VC_SESSION_STRING</code> to enable voice-chat playback.",
            parse_mode=ParseMode.HTML,
        )
        return
    played = await _play_next(update.effective_chat.id, context)
    if played:
        await update.effective_message.reply_text(f"<b>☾ 𝐍𝐎𝐖 𝐏𝐋𝐀𝐘𝐈𝐍𝐆</b>\n\n🎵 {played['title']}\n\n<i>The Oracle found your song.</i> 🌙", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("🌘 I found it, but the voice chat refused the handoff. Check that a VC is active and the assistant has permission to speak.")

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_player():
        await update.effective_message.reply_text("🌘 VC playback is not configured.")
        return
    try:
        await _calls.leave_call(update.effective_chat.id)
    except Exception:
        pass
    item = await _play_next(update.effective_chat.id, context)
    await update.effective_message.reply_text(f"⏭️ <b>SKIPPED.</b>\n{item['title'] if item else 'The queue is empty.'}", parse_mode=ParseMode.HTML)

async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = await storage.load(f"music:queue:{update.effective_chat.id}", [])
    if not items:
        await update.effective_message.reply_text("☾ The Midnight queue is empty.")
        return
    text = "<b>🎧 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐐𝐔𝐄𝐔𝐄</b>\n\n" + "\n".join(f"<b>{i+1}.</b> {x.get('title','Unknown')}" for i, x in enumerate(items[:10]))
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _ensure_player():
        try: await _calls.leave_call(update.effective_chat.id)
        except Exception: pass
    await storage.delete(f"music:queue:{update.effective_chat.id}")
    await update.effective_message.reply_text("☾ <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐀𝐃𝐈𝐎 𝐒𝐋𝐄𝐄𝐏𝐈𝐍𝐆</b>\n\n<i>The queue has been cleared.</i>", parse_mode=ParseMode.HTML)


def install(application) -> None:
    application.add_handler(CommandHandler(["midnightplay", "mplay"], play), group=20)
    application.add_handler(CommandHandler(["midnightskip", "mskip"], skip), group=20)
    application.add_handler(CommandHandler(["midnightqueue", "mqueue"], queue), group=20)
    application.add_handler(CommandHandler(["midnightstop", "mstop"], stop), group=20)
