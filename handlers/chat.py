"""Human-style Telegram chat with durable memory and a provider-independent Oracle Mind."""
from __future__ import annotations
import logging, os, time, random as _random, asyncio
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from core.ai import AIUnavailable
from core.chat import generate_reply as core_generate_reply
from core.oracle_mind import local_reply, recall_memories, save_explicit_memory
from handlers import storage

log=logging.getLogger("midnight.chat")
chat_enabled:dict[str,bool]={}; chat_persona:dict[str,str]={}; chat_history:dict[str,list[dict[str,str]]]={}; _last_reply_time:dict[str,float]={}
DEFAULT_PERSONA="friendly, casual, playful, naturally Hinglish when appropriate"
MAX_HISTORY=12; COOLDOWN_SECONDS=8; _AI_CONCURRENCY=2; _ai_slots=asyncio.Semaphore(_AI_CONCURRENCY); STORAGE_KEY="chat_settings"

async def load_from_storage():
    global chat_enabled, chat_persona
    saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}})
    if not isinstance(saved,dict): saved={}
    chat_enabled=dict(saved.get("enabled",{})); chat_persona=dict(saved.get("persona",{}))

async def _persist():
    await storage.save(STORAGE_KEY,{"enabled":chat_enabled,"persona":chat_persona})

async def toggle_chat(update,context):
    cid=str(update.effective_chat.id)
    async with storage.lock(f"chat-settings:{cid}") as acquired:
        if not acquired: return await update.message.reply_text("⏳ Just a second — I'm sorting the room out.",reply_to_message_id=update.message.message_id)
        saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}}); enabled=dict(saved.get("enabled",{})); personas=dict(saved.get("persona",{})); enabled[cid]=not bool(enabled.get(cid)); chat_enabled.update(enabled); chat_persona.update(personas); await storage.save(STORAGE_KEY,{"enabled":enabled,"persona":personas})
    await update.message.reply_text("Chat mode is now ON ✅" if enabled[cid] else "Chat mode is now OFF ❌",reply_to_message_id=update.message.message_id)

async def set_persona(update,context):
    cid=str(update.effective_chat.id); style=(" ".join(context.args).strip() if context.args else DEFAULT_PERSONA)[:300]
    chat_persona[cid]=style; await _persist(); await update.message.reply_text("Persona updated. 🌙",reply_to_message_id=update.message.message_id)

async def auto_reply(update,context):
    cid=str(update.effective_chat.id); msg=update.effective_message
    if not msg or not getattr(msg,"text",None): return
    text=msg.text.strip(); username=getattr(context.bot,"username",None)
    mentioned=bool(username and f"@{username}".casefold() in text.casefold())
    replied=bool(msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id==context.bot.id)
    explicitly_summoned=mentioned or replied or "midnight" in text.casefold() or "oracle" in text.casefold()
    if not chat_enabled.get(cid,False) and not explicitly_summoned:return
    now=time.monotonic()
    if now-_last_reply_time.get(cid,0)<COOLDOWN_SECONDS:return
    _last_reply_time[cid]=now
    persona=chat_persona.get(cid,DEFAULT_PERSONA); history=chat_history.setdefault(cid,[])
    user=msg.from_user
    speaker=" ".join(part for part in (getattr(user,"first_name",None),getattr(user,"last_name",None)) if part).strip() if user else "Member"
    speaker=speaker[:120] or "Member"
    history.append({"role":"user","speaker":speaker,"text":text[:1000]}); del history[:-MAX_HISTORY]
    db=context.application.bot_data.get("oracle_db")
    memories=[]
    if db and user:
        try:
            await save_explicit_memory(db,user.id,update.effective_chat.id,text)
            memories=await recall_memories(db,user.id,update.effective_chat.id,limit=6)
        except Exception: log.exception("ORACLE_MEMORY_UPDATE_FAILED | chat=%s",cid)
    try:
        async with _ai_slots: reply_text=await core_generate_reply(text,persona,history + ([{"role":"memory","speaker":"Oracle Memory","text":m} for m in memories] if memories else []))
    except AIUnavailable:
        reply_text=local_reply(text,history,memories); log.info("CHAT_PROVIDER_COOLDOWN | chat=%s | local_mind=true",cid)
    except Exception:
        reply_text=local_reply(text,history,memories); log.exception("CHAT_PROVIDER_INTERNAL_ERROR | chat=%s",cid)
    if not reply_text: reply_text=local_reply(text,history,memories)
    history.append({"role":"assistant","speaker":"Midnight Oracle","text":reply_text[:2000]}); del history[:-MAX_HISTORY]
    try: await msg.reply_text(reply_text,reply_to_message_id=msg.message_id)
    except Exception: log.exception("CHAT_SEND_FAILED | chat=%s",cid)

def _local_chat(text,history): return local_reply(text,history,None)

async def generate_reply(user_text,persona,history):return await core_generate_reply(user_text,persona,history)

def ai_service_configured():
    from core.ai import service
    return bool(service.api_key)

SAMPLE_STICKERS=["CAACAgUAAxkBAAEGBzJqdp9ai3sYNonxPitgXwW1HsGYLQACigEAAqMYnj7IByAbmW8_0z0E"]
_recent_stickers={}; GIF_SEARCH_TERMS=["funny reaction","excited","lol","confused","celebration","facepalm"]; REACTION_EMOJIS=["👍","🔥","🎉","👀","😁"]

def _pick_sticker(cid):
    recent=_recent_stickers.get(cid,[]); available=[s for s in SAMPLE_STICKERS if s not in recent] or SAMPLE_STICKERS; choice=_random.choice(available); recent.append(choice); _recent_stickers[cid]=recent[-4:]; return choice

async def get_sticker_id(update,context):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker:return await update.message.reply_text("Reply to a sticker with /getstickerid",reply_to_message_id=update.message.message_id)
    await update.message.reply_text(f"Sticker file_id:\n`{update.message.reply_to_message.sticker.file_id}`",reply_to_message_id=update.message.message_id)

async def send_random_sticker(update,context):
    if SAMPLE_STICKERS: await context.bot.send_sticker(update.effective_chat.id,_pick_sticker(str(update.effective_chat.id)),reply_to_message_id=update.message.message_id if update.message else None)

async def get_gif_url(term):
    key=os.getenv("GIPHY_API_KEY")
    if not key:return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r=await client.get("https://api.giphy.com/v1/gifs/search",params={"api_key":key,"q":term,"limit":8,"rating":"pg-13"});r.raise_for_status();data=r.json().get("data",[])
        return _random.choice(data).get("images",{}).get("original",{}).get("url") if data else None
    except Exception:log.exception("GIF_LOOKUP_FAILED");return None

async def send_random_gif(update,context):
    url=await get_gif_url(" ".join(context.args) if context.args else _random.choice(GIF_SEARCH_TERMS))
    if url: await context.bot.send_animation(update.effective_chat.id,url,reply_to_message_id=update.message.message_id if update.message else None)

async def get_image_url(term):
    """Find a safe, public image through Wikimedia Commons without another API key."""
    query=(term or "midnight oracle").strip()[:120]
    try:
        async with httpx.AsyncClient(timeout=12,headers={"User-Agent":"MidnightOracle/1.0"}) as client:
            r=await client.get("https://commons.wikimedia.org/w/api.php",params={"action":"query","format":"json","generator":"search","gsrsearch":query,"gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo","iiprop":"url|mime","iiurlwidth":1200})
            r.raise_for_status();pages=r.json().get("query",{}).get("pages",{})
        candidates=[]
        for page in pages.values():
            info=(page.get("imageinfo") or [{}])[0];mime=str(info.get("mime", ""));url=info.get("thumburl") or info.get("url")
            if url and mime.startswith("image/") and mime not in {"image/svg+xml","image/gif"}:candidates.append(url)
        return _random.choice(candidates) if candidates else None
    except Exception:log.exception("IMAGE_LOOKUP_FAILED");return None

async def image_command(update,context):
    term=" ".join(context.args).strip()
    if not term:return await update.effective_message.reply_text("🖼️ Usage: /image <what you want to see>",reply_to_message_id=update.effective_message.message_id)
    url=await get_image_url(term)
    if not url:return await update.effective_message.reply_text("☾ I couldn't find a clean image for that.",reply_to_message_id=update.effective_message.message_id)
    try: await context.bot.send_photo(update.effective_chat.id,url,reply_to_message_id=update.effective_message.message_id)
    except Exception:
        log.exception("IMAGE_SEND_FAILED");await update.effective_message.reply_text("☾ The image couldn't be delivered this time.",reply_to_message_id=update.effective_message.message_id)

async def maybe_react_to_message(update,context):
    if not update.message or not chat_enabled.get(str(update.effective_chat.id),False) or _random.random()>0.08:return
    try: await context.bot.set_message_reaction(chat_id=update.effective_chat.id,message_id=update.message.message_id,reaction=_random.choice(REACTION_EMOJIS))
    except Exception: pass

async def send_text_with_gif(update,context,text,term=None):
    if update.message:await update.message.reply_text(text,reply_to_message_id=update.message.message_id)
    if term:
        url=await get_gif_url(term)
        if url:await context.bot.send_animation(update.effective_chat.id,url,reply_to_message_id=update.message.message_id if update.message else None)

async def send_mood_gif(update,context):return await send_random_gif(update,context)
async def gif_reply(update,context):return await send_random_gif(update,context)
async def sticker_reply(update,context):return await send_random_sticker(update,context)