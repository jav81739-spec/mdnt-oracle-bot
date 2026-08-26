"""Midnight V2 voice-chat music engine.

The Telegram bot handles commands while a dedicated Pyrogram MTProto session
feeds PyTgCalls. Search is performed with yt-dlp and playback uses a remote
media URL, so tracks do not need to be permanently stored on disk.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from .storage import storage

log = logging.getLogger("midnight.vc")

try:
    from pyrogram import Client
    from pytgcalls import PyTgCalls
    from pytgcalls.types import AudioQuality, MediaStream, VideoQuality
except Exception:  # pragma: no cover - optional runtime dependency guard
    Client = PyTgCalls = MediaStream = AudioQuality = VideoQuality = None


@dataclass
class Track:
    title: str
    url: str
    webpage_url: str = ""
    duration: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "url": self.url, "webpage_url": self.webpage_url, "duration": self.duration}


class VCPlayer:
    def __init__(self) -> None:
        self.user_client = None
        self.calls = None
        self.started = False
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, chat_id: int) -> asyncio.Lock:
        return self._locks.setdefault(chat_id, asyncio.Lock())

    async def start(self) -> None:
        if self.started:
            return
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        session = os.getenv("TELEGRAM_SESSION_STRING")
        if not all((Client, PyTgCalls, MediaStream, api_id, api_hash, session)):
            log.warning("VC player disabled: MTProto credentials/session are not configured")
            return
        self.user_client = Client(
            "midnight-vc",
            api_id=int(api_id),
            api_hash=api_hash,
            session_string=session,
            in_memory=True,
        )
        await self.user_client.start()
        self.calls = PyTgCalls(self.user_client)
        self.calls.start()
        self.started = True
        log.info("Midnight VC engine online")

    async def stop(self) -> None:
        if self.calls:
            try:
                self.calls.stop()
            except Exception:
                log.exception("Failed stopping PyTgCalls")
        if self.user_client:
            try:
                await self.user_client.stop()
            except Exception:
                log.exception("Failed stopping VC MTProto client")
        self.started = False

    async def search(self, query: str) -> Track:
        import yt_dlp
        search = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "extract_flat": False,
            "skip_download": True,
        }
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(opts).extract_info(search, download=False))
        if not info:
            raise RuntimeError("No result found.")
        if "entries" in info:
            entries = [x for x in info.get("entries") or [] if x]
            if not entries:
                raise RuntimeError("No result found.")
            info = entries[0]
        url = info.get("url")
        if not url:
            raise RuntimeError("The selected track has no playable audio stream.")
        return Track(
            title=str(info.get("title") or "Unknown track"),
            url=str(url),
            webpage_url=str(info.get("webpage_url") or ""),
            duration=int(info.get("duration") or 0),
        )

    async def play(self, chat_id: int, track: Track) -> None:
        if not self.started or not self.calls:
            raise RuntimeError("VC player is not configured. Ask the owner to configure the MTProto session.")
        async with self._lock(chat_id):
            await self.calls.play(
                chat_id,
                MediaStream(
                    track.url,
                    AudioQuality.HIGH,
                    VideoQuality.HD_720p,
                    video_flags=MediaStream.Flags.IGNORE,
                ),
            )
            await storage.set(f"vc:now:{chat_id}", track.as_dict(), ttl=6 * 3600)

    async def stop_call(self, chat_id: int) -> None:
        if not self.started or not self.calls:
            raise RuntimeError("VC player is not configured.")
        await self.calls.leave_call(chat_id)
        await storage.delete(f"vc:now:{chat_id}")

    async def pause(self, chat_id: int) -> None:
        if not self.started or not self.calls:
            raise RuntimeError("VC player is not configured.")
        await self.calls.pause(chat_id)

    async def resume(self, chat_id: int) -> None:
        if not self.started or not self.calls:
            raise RuntimeError("VC player is not configured.")
        await self.calls.resume(chat_id)


player = VCPlayer()


def _chat(update: Update) -> int:
    return int(update.effective_chat.id)


async def midnightplay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text("🎧 <b>Midnight Radio</b>\n\nUsage: <code>/midnightplay song name</code>", parse_mode=ParseMode.HTML)
        return
    try:
        track = await player.search(query)
        await player.play(_chat(update), track)
    except Exception as exc:
        log.warning("VC play failed: %s", exc)
        await update.effective_message.reply_text(f"🌘 <b>Radio couldn't start.</b>\n\n<code>{str(exc)[:180]}</code>", parse_mode=ParseMode.HTML)
        return
    await update.effective_message.reply_text(
        f"🎧 <b>𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐑𝐀𝐃𝐈𝐎</b>\n\n▶️ <b>{track.title}</b>\n\n<i>Now playing in the voice chat.</i> 🌙",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def nowplaying(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track = await storage.load(f"vc:now:{_chat(update)}", None)
    if not isinstance(track, dict):
        await update.effective_message.reply_text("🌘 Midnight Radio is currently silent.")
        return
    await update.effective_message.reply_text(f"🎧 <b>NOW PLAYING</b>\n\n<b>{track.get('title','Unknown')}</b>\n\n☾ Midnight Radio", parse_mode=ParseMode.HTML)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await player.stop_call(_chat(update))
    except Exception as exc:
        await update.effective_message.reply_text(f"🌘 {str(exc)[:180]}")
        return
    await update.effective_message.reply_text("⏹️ <b>Midnight Radio</b> has gone quiet. 🌙", parse_mode=ParseMode.HTML)


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await player.pause(_chat(update))
    except Exception as exc:
        await update.effective_message.reply_text(f"🌘 {str(exc)[:180]}")
        return
    await update.effective_message.reply_text("⏸️ Paused. The night is holding its breath. 🌙")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await player.resume(_chat(update))
    except Exception as exc:
        await update.effective_message.reply_text(f"🌘 {str(exc)[:180]}")
        return
    await update.effective_message.reply_text("▶️ Resumed. Midnight Radio is alive again. 🌙")


def install(application) -> None:
    application.add_handler(CommandHandler(["midnightplay", "play"], midnightplay), group=18)
    application.add_handler(CommandHandler(["nowplaying", "np"], nowplaying), group=18)
    application.add_handler(CommandHandler(["stopmusic", "vcstop"], stop), group=18)
    application.add_handler(CommandHandler(["pausemusic", "vcpause"], pause), group=18)
    application.add_handler(CommandHandler(["resumemusic", "vcresume"], resume), group=18)
