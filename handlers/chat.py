"""Human-style Telegram chat plus the legacy media/reaction surface."""
from __future__ import annotations

import logging
import os
import time
import random as _random

import httpx
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
    if not isinstance(saved, dict): saved = {}
    chat_enabled = dict(saved.get("enabled", {})); chat_persona = dict(saved.get("persona", {}))


async def _persist() -> None:
    if not await storage.save(STORAGE_KEY, {"enabled": chat_enabled, "persona": chat_persona}):
        raise RuntimeError("chat settings could not be persisted")


async def toggle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    async with storage.lock(f"chat-settings:{chat_id}") as acquired:
        if not acquired: await update.message.reply_text("⏳ Chat settings are busy — try again."); return
        saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}}); enabled=dict(saved.get("enabled",{})) if isinstance(saved,dict) else {}; personas=dict(saved.get("persona",{})) if isinstance(saved,dict) else {}
        enabled[chat_id]=not bool(enabled.get(chat_id,False)); chat_enabled.update(enabled); chat_persona.update(personas)
        if not await storage.save(STORAGE_KEY,{"enabled":enabled,"persona":personas}): raise RuntimeError("chat settings could not be persisted")
        state="ON ✅" if enabled[chat_id] else "OFF ❌"
    await update.message.reply_text(f"Chat mode is now {state}\n_(saved across restarts)_",parse_mode="Markdown")


async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=str(update.effective_chat.id); style=(" ".join(context.args).strip() if context.args else DEFAULT_PERSONA)[:300]
    async with storage.lock(f"chat-settings:{chat_id}") as acquired:
        if not acquired: await update.message.reply_text("⏳ Chat settings are busy — try again."); return
        saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}}); enabled=dict(saved.get("enabled",{})) if isinstance(saved,dict) else {}; personas=dict(saved.get("persona",{})) if isinstance(saved,dict) else {}; personas[chat_id]=style; chat_enabled.update(enabled); chat_persona.update(personas)
        if not await storage.save(STORAGE_KEY,{"enabled":enabled,"persona":personas}): raise RuntimeError("chat settings could not be persisted")
    await update.message.reply_text(f"Persona updated: {style}")


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=str(update.effective_chat.id)
    if not chat_enabled.get(chat_id,False) or not update.message or not update.message.text: return
    message=update.message; bot_username=context.bot.username
    mentioned=bool(bot_username and f"@{bot_username}" in message.text); replied=bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id==context.bot.id)
    if not (mentioned or replied or "midnight" in message.text.lower()): return
    now=time.monotonic()
    if now-_last_reply_time.get(chat_id,0.0)<COOLDOWN_SECONDS: return
    _last_reply_time[chat_id]=now; persona=chat_persona.get(chat_id,DEFAULT_PERSONA); history=chat_history.setdefault(chat_id,[]); history.append({"role":"user","text":message.text[:1000]}); del history[:-MAX_HISTORY]
    try: reply_text=await generate_reply(message.text,persona,history)
    except AIUnavailable as exc: log.info("AI unavailable for chat=%s: %s",chat_id,exc); await message.reply_text("🌙 my signal is a little weak right now — try again in a moment."); return
    except Exception: log.exception("Unexpected AI chat failure for chat=%s",chat_id); await message.reply_text("🌙 something tangled the signal — try that again."); return
    if not reply_text: await message.reply_text("🔌 AI chat needs a GEMINI_API_KEY in the deployment environment."); return
    history.append({"role":"assistant","text":reply_text[:2000]}); del history[:-MAX_HISTORY]; await message.reply_text(reply_text)


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    if not ai_service_configured(): return None
    return await core_generate_reply(user_text,persona,history)


def ai_service_configured() -> bool:
    from core.ai import service
    return bool(service.api_key)


SAMPLE_STICKERS = [
    "CAACAgUAAxkBAAEGBzJqdp9ai3sYNonxPitgXwW1HsGYLQACigEAAqMYnj7IByAbmW8_0z0E",
    "CAACAgUAAxkBAAEGBzBqdp8mL5Juj0jyC3nh7q2mdBwJbAACyRMAAlJekFeBRat3I0udiz0E",
    "CAACAgUAAxkBAAEGBy5qdp8Uv6Pi3-VK9BJ7nn8_08Ju5wACsQQAAqQhMVYQIkv-OAABHc49BA",
    "CAACAgUAAxkBAAEGByxqdp7ystKCl2Rj7YKklllelMrR2gACqRUAAkggCFejMbHj9ySCNj0E",
    "CAACAgUAAxkBAAEGByZqdp6sg55QIGUcBVbW5ZvbvR1B8QACFhEAAlYTiVduxmgSyR8nUT0E",
    "CAACAgUAAxkBAAEGBxxqdp587c9-Vw1hftneSbQ9pWWtXQAC5BgAAremsVRaWlNEWRIuZz0E",
    "CAACAgUAAxkBAAEGBxpqdp5twHyvyAABbNEdbXdkTXCb7eAAAukaAAK32rhVVsDSda6ab2w9BA",
    "CAACAgUAAxkBAAEGBzRqdp_FeJQQ3EJfKq_Y7fZ-5l9lngAC5wEAAq4xRgWFtzPKdb1ZuD0E",
    "CAACAgUAAxkBAAEGBzZqdp_rySrqxo6FHWJ7J7VCq9HesAAC_xAAAn9jEVbXO-B4ukFDLz0E",
    "CAACAgUAAxkBAAEGBzhqdqAQk68E9J2t0sf1bwMizD3_ogACqgMAAnC-SFblo1QW5PoU0D0E",
    "CAACAgUAAxkBAAEGDn9qeGY4_JoN1L6EAu56kQPx5H8hhgACCgQAAsIkiFcGn8ZlVTJpDz0E",
]
_recent_stickers: dict[str,list[str]]={}
GIF_SEARCH_TERMS=["funny reaction","excited","lol","confused","celebration","facepalm"]
REACTION_EMOJIS=["👍","🔥","🎉","👀","😁"]


def _pick_sticker(chat_id:str)->str:
    recent=_recent_stickers.get(chat_id,[]); available=[s for s in SAMPLE_STICKERS if s not in recent] or SAMPLE_STICKERS; choice=_random.choice(available); recent.append(choice); _recent_stickers[chat_id]=recent[-4:]; return choice

async def get_sticker_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker: await update.message.reply_text("Reply to a sticker with /getstickerid to grab its ID"); return
    await update.message.reply_text(f"📎 Sticker file_id:\n`{update.message.reply_to_message.sticker.file_id}`",parse_mode="Markdown")

async def send_random_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SAMPLE_STICKERS: await update.message.reply_text("🎨 No sticker IDs are configured."); return
    await context.bot.send_sticker(update.effective_chat.id,_pick_sticker(str(update.effective_chat.id)))

async def get_gif_url(term:str)->str|None:
    api_key=os.getenv("GIPHY_API_KEY")
    if not api_key: return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp=await client.get("https://api.giphy.com/v1/gifs/search",params={"q":term,"api_key":api_key,"limit":15,"rating":"pg-13"}); resp.raise_for_status(); results=resp.json().get("data",[])
        return _random.choice(results)["images"]["original"]["url"] if results else None
    except (httpx.HTTPError,ValueError,KeyError,IndexError): return None

async def send_text_with_gif(bot,chat_id:int,text:str,term:str,parse_mode:str="Markdown",reply_to_message_id:int|None=None):
    gif_url=await get_gif_url(term)
    if gif_url: await bot.send_animation(chat_id,gif_url,caption=text,parse_mode=parse_mode,reply_to_message_id=reply_to_message_id)
    else: await bot.send_message(chat_id,text,parse_mode=parse_mode,reply_to_message_id=reply_to_message_id)

async def send_mood_gif(bot,chat_id:int,term:str):
    gif_url=await get_gif_url(term)
    if gif_url: await bot.send_animation(chat_id,gif_url)

async def send_random_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.getenv("GIPHY_API_KEY"): await update.message.reply_text("🎬 GIFs need a free GIPHY_API_KEY."); return
    term=" ".join(context.args) if context.args else _random.choice(GIF_SEARCH_TERMS); gif_url=await get_gif_url(term)
    if not gif_url: await update.message.reply_text(f"No GIFs found for '{term}' — try a different term."); return
    await context.bot.send_animation(update.effective_chat.id,gif_url)

async def gif_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not chat_enabled.get(str(update.effective_chat.id),False): return
    if not (update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id==context.bot.id): return
    gif_url=await get_gif_url(_random.choice(GIF_SEARCH_TERMS))
    if gif_url: await context.bot.send_animation(update.effective_chat.id,gif_url,reply_to_message_id=update.message.message_id)

async def maybe_react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not chat_enabled.get(str(update.effective_chat.id),False) or _random.random()>0.08: return
    try: await context.bot.set_message_reaction(chat_id=update.effective_chat.id,message_id=update.message.message_id,reaction=_random.choice(REACTION_EMOJIS))
    except Exception as exc: log.info("Reaction unavailable: %s",exc)

async def sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=str(update.effective_chat.id)
    if not chat_enabled.get(chat_id,False): return
    if not (update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id==context.bot.id): return
    if SAMPLE_STICKERS: await context.bot.send_sticker(update.effective_chat.id,_pick_sticker(chat_id),reply_to_message_id=update.message.message_id)
