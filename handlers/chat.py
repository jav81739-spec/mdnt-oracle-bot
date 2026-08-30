"""Human-style Telegram chat with a provider-independent conversation path."""
from __future__ import annotations
import logging, os, time, random as _random, asyncio
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from core.ai import AIUnavailable
from core.chat import generate_reply as core_generate_reply
from handlers import storage

log=logging.getLogger("midnight.chat")
chat_enabled:dict[str,bool]={}; chat_persona:dict[str,str]={}; chat_history:dict[str,list[dict[str,str]]]={}; _last_reply_time:dict[str,float]={}
DEFAULT_PERSONA="friendly, casual, playful, naturally Hinglish when appropriate"
MAX_HISTORY=10; COOLDOWN_SECONDS=8; _AI_CONCURRENCY=2; _ai_slots=asyncio.Semaphore(_AI_CONCURRENCY); STORAGE_KEY="chat_settings"

async def load_from_storage():
    global chat_enabled,chat_persona
    saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}})
    if not isinstance(saved,dict): saved={}
    chat_enabled=dict(saved.get("enabled",{})); chat_persona=dict(saved.get("persona",{}))

async def _persist():
    await storage.save(STORAGE_KEY,{"enabled":chat_enabled,"persona":chat_persona})

async def toggle_chat(update,context):
    cid=str(update.effective_chat.id)
    async with storage.lock(f"chat-settings:{cid}") as acquired:
        if not acquired: return await update.message.reply_text("⏳ Just a second — I'm sorting the room out.")
        saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}}); enabled=dict(saved.get("enabled",{})); personas=dict(saved.get("persona",{})); enabled[cid]=not bool(enabled.get(cid)); chat_enabled.update(enabled); chat_persona.update(personas); await storage.save(STORAGE_KEY,{"enabled":enabled,"persona":personas})
    await update.message.reply_text("Chat mode is now ON ✅" if enabled[cid] else "Chat mode is now OFF ❌")

async def set_persona(update,context):
    cid=str(update.effective_chat.id); style=(" ".join(context.args).strip() if context.args else DEFAULT_PERSONA)[:300]
    chat_persona[cid]=style; await _persist(); await update.message.reply_text("Persona updated. 🌙")

async def auto_reply(update,context):
    cid=str(update.effective_chat.id)
    if not chat_enabled.get(cid,False) or not update.message or not update.message.text: return
    msg=update.message; username=context.bot.username
    mentioned=bool(username and f"@{username}" in msg.text); replied=bool(msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id==context.bot.id)
    if not (mentioned or replied or "midnight" in msg.text.lower()): return
    now=time.monotonic()
    if now-_last_reply_time.get(cid,0.0)<COOLDOWN_SECONDS: return
    _last_reply_time[cid]=now
    persona=chat_persona.get(cid,DEFAULT_PERSONA); history=chat_history.setdefault(cid,[]); history.append({"role":"user","text":msg.text[:1000]}); del history[:-MAX_HISTORY]
    try:
        async with _ai_slots:
            reply_text=await core_generate_reply(msg.text,persona,history)
    except AIUnavailable:
        reply_text=_local_chat(msg.text,history)
        log.info("CHAT_PROVIDER_COOLDOWN | chat=%s | local_engine=true",cid)
    except Exception:
        reply_text=_local_chat(msg.text,history)
        log.exception("CHAT_PROVIDER_INTERNAL_ERROR | chat=%s",cid)
    if not reply_text: reply_text=_local_chat(msg.text,history)
    history.append({"role":"assistant","text":reply_text[:2000]}); del history[:-MAX_HISTORY]
    try: await msg.reply_text(reply_text)
    except Exception: log.exception("CHAT_SEND_FAILED | chat=%s",cid)


def _local_chat(text,history):
    t=(text or "").strip()
    if not t: return "I'm here. 🌙"
    last=[x.get("text","") for x in history[-4:] if x.get("role")=="user"]
    if "?" in t: return "Haan, let's unpack that. 🌙"
    if any(x in t.lower() for x in ("sad","upset","rough","bad day","not okay","😭","🥲")): return "Haan… bol. Main sun raha hoon. 🖤"
    if any(x in t.lower() for x in ("lol","haha","😂","🤣")): return "😂 Okay, that one actually got me."
    if last and last[-1] != t: return "I'm with you. Keep going. 🌙"
    return "Hmm. Tell me more."

async def generate_reply(user_text,persona,history):
    return await core_generate_reply(user_text,persona,history)

def ai_service_configured():
    from core.ai import service
    return bool(service.api_key)

SAMPLE_STICKERS=[
    "CAACAgUAAxkBAAEGBzJqdp9ai3sYNonxPitgXwW1HsGYLQACigEAAqMYnj7IByAbmW8_0z0E",
]
_recent_stickers={}; GIF_SEARCH_TERMS=["funny reaction","excited","lol","confused","celebration","facepalm"]; REACTION_EMOJIS=["👍","🔥","🎉","👀","😁"]

def _pick_sticker(cid):
    recent=_recent_stickers.get(cid,[]); available=[s for s in SAMPLE_STICKERS if s not in recent] or SAMPLE_STICKERS; choice=_random.choice(available); recent.append(choice); _recent_stickers[cid]=recent[-4:]; return choice

async def get_sticker_id(update,context):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker: return await update.message.reply_text("Reply to a sticker with /getstickerid")
    await update.message.reply_text(f"Sticker file_id:\n`{update.message.reply_to_message.sticker.file_id}`")

async def send_random_sticker(update,context):
    if SAMPLE_STICKERS: await context.bot.send_sticker(update.effective_chat.id,_pick_sticker(str(update.effective_chat.id)))

async def get_gif_url(term):
    key=os.getenv("GIPHY_API_KEY")
    if not key:return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r=await client.get("https://api.giphy.com/v1/gifs/search",params={"q":term,"api_key":key,"limit":15,"rating":"pg-13"}); r.raise_for_status(); data=r.json().get("data",[])
        return _random.choice(data)["images"]["original"]["url"] if data else None
    except Exception:return None

async def send_random_gif(update,context):
    url=await get_gif_url(" ".join(context.args) if context.args else _random.choice(GIF_SEARCH_TERMS))
    if url: await context.bot.send_animation(update.effective_chat.id,url)

async def maybe_react_to_message(update,context):
    if not update.message or not chat_enabled.get(str(update.effective_chat.id),False) or _random.random()>0.08:return
    try: await context.bot.set_message_reaction(chat_id=update.effective_chat.id,message_id=update.message.message_id,reaction=_random.choice(REACTION_EMOJIS))
    except Exception: pass


# Compatibility surface retained for the established legacy runtime.
async def send_text_with_gif(update, context, text: str, term: str | None = None):
    """Send text and, when available, a matching GIF without requiring a provider."""
    if update.message:
        await update.message.reply_text(text)
    if term:
        url = await get_gif_url(term)
        if url:
            await context.bot.send_animation(update.effective_chat.id, url)


async def send_mood_gif(update, context):
    """Compatibility wrapper for the existing random-GIF command surface."""
    return await send_random_gif(update, context)


async def gif_reply(update, context):
    """Compatibility wrapper for legacy GIF replies."""
    return await send_random_gif(update, context)


async def sticker_reply(update, context):
    """Compatibility wrapper for legacy sticker replies."""
    return await send_random_sticker(update, context)
