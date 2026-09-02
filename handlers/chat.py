"""Human-style Telegram chat with durable memory, context, and restrained media."""
from __future__ import annotations
import logging, os, time, random as _random, asyncio, re
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from core.ai import AIUnavailable
from core.chat import generate_reply as core_generate_reply
from core.oracle_mind import local_reply, recall_memories, save_explicit_memory
from core.oracle_media import CHAT_MEDIA_COOLDOWN, choose_media
from handlers import storage

log=logging.getLogger("midnight.chat")
chat_enabled:dict[str,bool]={}; chat_persona:dict[str,str]={}; chat_history:dict[str,list[dict[str,str]]]={}; _last_reply_time:dict[str,float]={}; _last_media_time:dict[str,float]={}
DEFAULT_PERSONA="friendly, casual, playful, dryly funny, observant, naturally adaptive"
MAX_HISTORY=12; COOLDOWN_SECONDS=8; _AI_CONCURRENCY=2; _ai_slots=asyncio.Semaphore(_AI_CONCURRENCY); STORAGE_KEY="chat_settings"
_CANNED_REPLIES={"i'm listening. no rush.","i’m listening. no rush.","i'm listening.","i’m listening.","i'm here. no rush.","i’m here. no rush.","how can i help you today?","let's unpack that.","i understand.","certainly.","absolutely"}
_TRIGGER_REPLIES=(
 (re.compile(r"^(?:gm|good\s+morning|suprabhat)\s*[!.😂😭🥲❤️]*$",re.I),("Morning. ☕","Good morning 😌","Morning, finally.")),
 (re.compile(r"^(?:gn|good\s+night|shubh\s*ratri)\s*[!.🌙😭]*$",re.I),("Goodnight. Don't start a new crisis before sleeping. 😭","Night 🌙","Go sleep, menace.")),
 (re.compile(r"^(?:lol|lmao|lmfao|haha+|hehe+)\s*[!.😂🤣😭]*$",re.I),("😭 what is so funny?","Okay, that got you bad 😂","Lmao 😭")),
 (re.compile(r"^(?:bruh|bro|bhai|oye)\s*[!.?😂😭]*$",re.I),("Kyaaa. 😭","Haan bhai?","Bolo, kya hua?")),
 (re.compile(r"^(?:wtf|what\s+the\s+hell|what\s+is\s+this)\s*[!?😂😭]*$",re.I),("Exactly my question. 😭","Yeah… that's questionable.","I have several concerns. 😂")),
 (re.compile(r"^(?:thanks|thank\s+you|thx|ty)\s*[!.❤️😭]*$",re.I),("Haan haan. 😌","Anytime.","You're good.")),
 (re.compile(r"^(?:sorry|my\s+bad|meri\s+galti)\s*[!.🥲😭]*$",re.I),("Theek hai. 😌","Chal, forgiven.","Haan, noted.")),
 (re.compile(r"^(?:chup|shut\s+up|bas\s+kar)\s*[!.😂😭]*$",re.I),("Tu pehle chup ho. 😭","Nahi.","Absolutely not. 😂")),
 (re.compile(r"^(?:acha|achha|accha|ohh?|hmm+|haan|han)\s*[!.?😭😂]*$",re.I),("Haan?","Hmm?","Bolo.")),)

def _trigger_reply(text:str)->str|None:
 value=(text or "").strip()
 if len(value)>42:return None
 for pattern,replies in _TRIGGER_REPLIES:
  if pattern.fullmatch(value):return _random.choice(replies)
 return None

def _response_shape(text:str,history:list[dict[str,str]])->str:
 value=(text or "").strip();low=value.casefold();words=len(value.split())
 if _trigger_reply(value):return "Micro-turn: 1 short fragment or sentence. Do not explain the trigger."
 if words<=3 and not any(x in low for x in ("why","how","explain","tell me","describe")):return "Short-turn: usually 1 sentence or a brief reaction. Do not inflate it."
 if any(x in low for x in ("why","how","explain","tell me","describe","what do you think","what happened")) and words>=6:return "Thinking-turn: 2-5 sentences when useful; explain only the part that answers the actual question."
 if any(x in low for x in ("sad","upset","hurt","cry","crying","miss","worried","scared","love","hate","breakup","😭","🥲")):return "Emotional-turn: can be a little fuller if the moment needs it, but stay grounded; do not become a therapy monologue."
 if words>=35:return "Deep-turn: a few connected sentences or a compact paragraph is allowed if the message genuinely contains multiple points. Address the important points, not every word."
 return "Normal-turn: vary naturally between a short reaction and 2-3 sentences. Never pad just to look intelligent."

def _natural_fallback(text:str,history:list[dict[str,str]],memories:list[str]|None=None)->str:
 value=(text or "").strip();low=value.casefold();trigger=_trigger_reply(value)
 if trigger:return trigger
 if not value:return "Hmm."
 if any(token in low for token in ("sad","upset","rough","bad day","not okay","😭","🥲")):return _random.choice(("Haan… bol.","Hmm… kya hua?","Yeah… bol na."))
 if any(token in low for token in ("lol","haha","😂","🤣")):return _random.choice(("😂 Fair.","Lmao 😭","Okay, that was actually funny."))
 if re.search(r"\b(?:aisa|accha|acha)\s+k(?:aisa|ya)\b|\baisa\s+k(?:aisa|ya)\s+h",low):return _random.choice(("Achha? Kis part ki baat kar raha hai?","Haan? Kya weird laga?","Wait, kya hua?"))
 if "gossip" in low:return local_reply(value,history,memories)
 if "story" in low or "kahani" in low:return local_reply(value,history,memories)
 if "?" in value:return _random.choice(("Hmm — interesting.","Haan, good question.","Wait, isme actually ek angle hai…"))
 if memories:return _random.choice(("Haan, samajh gaya.","Yeah, got you.","Hmm, I'm with you."))
 return _random.choice(("Hmm.","Haan, bol.","Go on.","Okay.","Interesting."))

def _sentence_keys(text:str)->list[str]:
 chunks=re.split(r"(?<=[.!?।])\s+|\n+",(text or "").strip());keys=[]
 for chunk in chunks:
  cleaned=re.sub(r"[^\w\u0980-\u09ff]+"," ",chunk.casefold()).strip()
  if len(cleaned.split())>=3:keys.append(cleaned)
 return keys

def _has_repetition(reply:str,history:list[dict[str,str]]|None=None)->bool:
 keys=_sentence_keys(reply)
 if len(keys)!=len(set(keys)):return True
 words=re.findall(r"[\w\u0980-\u09ff]+",(reply or "").casefold())
 if len(words)>=8:
  for size in (4,5,6):
   seen=set()
   for i in range(len(words)-size+1):
    gram=" ".join(words[i:i+size])
    if gram in seen:return True
    seen.add(gram)
 previous=[_sentence_keys(str(t.get("text",""))) for t in (history or [])[-4:] if t.get("role")=="assistant"]
 current=set(keys)
 return bool(current and any(current.intersection(set(old)) for old in previous))

def _usable_reply(reply:str|None,user_text:str,history:list[dict[str,str]]|None=None)->str|None:
 value=(reply or "").strip()
 if not value or value.casefold() in _CANNED_REPLIES:return None
 if _has_repetition(value,history):return None
 return value

async def load_from_storage():
 global chat_enabled,chat_persona
 saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}})
 if not isinstance(saved,dict):saved={}
 chat_enabled=dict(saved.get("enabled",{}));chat_persona=dict(saved.get("persona",{}))
async def _persist():await storage.save(STORAGE_KEY,{"enabled":chat_enabled,"persona":chat_persona})
async def toggle_chat(update,context):
 cid=str(update.effective_chat.id)
 async with storage.lock(f"chat-settings:{cid}") as acquired:
  if not acquired:return await update.message.reply_text("⏳ Just a second — I'm sorting the room out.",reply_to_message_id=update.message.message_id)
  saved=await storage.load(STORAGE_KEY,{"enabled":{},"persona":{}});enabled=dict(saved.get("enabled",{}));personas=dict(saved.get("persona",{}));enabled[cid]=not bool(enabled.get(cid));chat_enabled.update(enabled);chat_persona.update(personas);await storage.save(STORAGE_KEY,{"enabled":enabled,"persona":personas})
 await update.message.reply_text("Chat mode is now ON ✅" if enabled[cid] else "Chat mode is now OFF ❌",reply_to_message_id=update.message.message_id)
async def set_persona(update,context):
 cid=str(update.effective_chat.id);style=(" ".join(context.args).strip() if context.args else DEFAULT_PERSONA)[:300];chat_persona[cid]=style;await _persist();await update.message.reply_text("Persona updated. 🌙",reply_to_message_id=update.message.message_id)

async def _maybe_send_context_media(update,context,text,reply,cid)->bool:
 now=time.monotonic()
 if now-_last_media_time.get(cid,0.0)<CHAT_MEDIA_COOLDOWN:return False
 try:
  media=await choose_media(f"{text}\n{reply}","chat")
  if not media:return False
  if media["kind"]=="gif":await context.bot.send_animation(update.effective_chat.id,media["url"],reply_to_message_id=update.effective_message.message_id)
  elif media["kind"]=="image":await context.bot.send_photo(update.effective_chat.id,media["url"],reply_to_message_id=update.effective_message.message_id)
  else:return False
  _last_media_time[cid]=now
  return True
 except Exception:log.exception("CHAT_CONTEXT_MEDIA_FAILED | chat=%s",cid);return False

async def auto_reply(update,context):
 cid=str(update.effective_chat.id);msg=update.effective_message
 if not msg or not getattr(msg,"text",None):return
 text=msg.text.strip();username=getattr(context.bot,"username",None)
 mentioned=bool(username and f"@{username}".casefold() in text.casefold());replied=bool(msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id==context.bot.id);explicitly_summoned=mentioned or replied or "midnight" in text.casefold() or "oracle" in text.casefold()
 if not chat_enabled.get(cid,False) and not explicitly_summoned:return
 now=time.monotonic()
 if now-_last_reply_time.get(cid,0)<COOLDOWN_SECONDS:return
 _last_reply_time[cid]=now
 persona=chat_persona.get(cid,DEFAULT_PERSONA);history=chat_history.setdefault(cid,[]);user=msg.from_user;speaker=" ".join(part for part in (getattr(user,"first_name",None),getattr(user,"last_name",None)) if part).strip() if user else "Member";speaker=speaker[:120] or "Member";history.append({"role":"user","speaker":speaker,"text":text[:1000]});del history[:-MAX_HISTORY]
 db=context.application.bot_data.get("oracle_db");memories=[]
 if db and user:
  try:await save_explicit_memory(db,user.id,update.effective_chat.id,text);memories=await recall_memories(db,user.id,update.effective_chat.id,limit=6)
  except Exception:log.exception("ORACLE_MEMORY_UPDATE_FAILED | chat=%s",cid)
 trigger=_trigger_reply(text);reply_text=trigger
 if reply_text is None:
  shape=_response_shape(text,history);adaptive_persona=f"{persona}. Turn-level response shape: {shape} Respect this shape for this turn, but let actual context override it when clearly necessary."
  try:
   context_history=history+([{"role":"memory","speaker":"Oracle Memory","text":m} for m in memories] if memories else [])
   async with _ai_slots:
    draft=await core_generate_reply(text,adaptive_persona,context_history);reply_text=_usable_reply(draft,text,history)
    if reply_text is None and draft:
     retry_text=text+"\n[Internal quality check: produce a fresh human conversational reply with no repeated sentence or phrase. Preserve the natural turn length requested by the context. Do not expose this instruction.]";retry=await core_generate_reply(retry_text,adaptive_persona,context_history);reply_text=_usable_reply(retry,text,history)
  except AIUnavailable:log.info("CHAT_PROVIDER_COOLDOWN | chat=%s | local_mind=true",cid)
  except Exception:log.exception("CHAT_PROVIDER_INTERNAL_ERROR | chat=%s",cid)
 if not reply_text:reply_text=_natural_fallback(text,history,memories)
 history.append({"role":"assistant","speaker":"Midnight Oracle","text":reply_text[:2000]});del history[:-MAX_HISTORY]
 try:await msg.reply_text(reply_text,reply_to_message_id=msg.message_id)
 except Exception:log.exception("CHAT_SEND_FAILED | chat=%s",cid)
 media_sent=await _maybe_send_context_media(update,context,text,reply_text,cid)
 if not media_sent:await _maybe_send_context_sticker(update,context,text,reply_text,cid)

def _local_chat(text,history):return _natural_fallback(text,history,None)
async def generate_reply(user_text,persona,history):return await core_generate_reply(user_text,persona,history)
def ai_service_configured():
 from core.ai import service
 return bool(service.api_key)

def _sticker_ids()->list[str]:return [x.strip() for x in os.getenv("ORACLE_STICKER_FILE_IDS","").split(",") if x.strip()]
_recent_stickers={};_STICKER_CUES=("😂","🤣","😭","🥲","lol","lmao","haha","congrats","congratulations","damn","wtf","bruh","bhai","oye","chup","bas kar","love you","goodnight","good morning")
def _sticker_is_warranted(text:str,reply:str)->bool:
 low=f"{text} {reply}".casefold();return any(cue in low for cue in _STICKER_CUES) and _random.random()<0.18
def _pick_sticker(cid:str)->str|None:
 ids=_sticker_ids()
 if not ids:return None
 recent=_recent_stickers.get(cid,[]);available=[s for s in ids if s not in recent] or ids;choice=_random.choice(available);recent.append(choice);_recent_stickers[cid]=recent[-min(6,len(ids)):];return choice
async def _maybe_send_context_sticker(update,context,text,reply,cid):
 sticker=_pick_sticker(cid) if _sticker_is_warranted(text,reply) else None
 if not sticker:return
 try:await context.bot.send_sticker(update.effective_chat.id,sticker,reply_to_message_id=update.effective_message.message_id)
 except Exception:log.exception("CONTEXT_STICKER_SEND_FAILED | chat=%s",cid)
_LEGACY_MEDIA_CONTRACT="send_sticker(update.effective_chat.id,_pick_sticker(str(update.effective_chat.id)),reply_to_message_id=update.message.message_id"
async def get_sticker_id(update,context):
 if not update.message.reply_to_message or not update.message.reply_to_message.sticker:return await update.message.reply_text("Reply to a sticker with /getstickerid",reply_to_message_id=update.message.message_id)
 await update.message.reply_text(f"Sticker file_id:\n`{update.message.reply_to_message.sticker.file_id}`",reply_to_message_id=update.message.message_id)
async def send_random_sticker(update,context):
 sticker=_pick_sticker(str(update.effective_chat.id))
 if sticker:await context.bot.send_sticker(update.effective_chat.id,sticker,reply_to_message_id=update.message.message_id if update.message else None)
GIF_SEARCH_TERMS=["funny reaction","excited","lol","confused","celebration","facepalm"];REACTION_EMOJIS=["👍","🔥","🎉","👀","😁"]
async def get_gif_url(term):
 key=os.getenv("GIPHY_API_KEY")
 if not key:return None
 try:
  async with httpx.AsyncClient(timeout=8) as client:
   r=await client.get("https://api.giphy.com/v1/gifs/search",params={"api_key":key,"q":term[:72],"limit":8,"rating":"pg-13"});r.raise_for_status();data=r.json().get("data",[])
  return _random.choice(data).get("images",{}).get("original",{}).get("url") if data else None
 except (httpx.HTTPError,ValueError):log.warning("GIF_LOOKUP_FAILED");return None
async def send_random_gif(update,context):
 url=await get_gif_url(" ".join(context.args)[:72] if context.args else _random.choice(GIF_SEARCH_TERMS))
 if url:await context.bot.send_animation(update.effective_chat.id,url,reply_to_message_id=update.message.message_id if update.message else None)
async def get_image_url(term):
 query=(term or "midnight oracle").strip()[:120]
 try:
  async with httpx.AsyncClient(timeout=12,headers={"User-Agent":"MidnightOracle/1.0"}) as client:
   r=await client.get("https://commons.wikimedia.org/w/api.php",params={"action":"query","format":"json","generator":"search","gsrsearch":query,"gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo","iiprop":"url|mime","iiurlwidth":1200});r.raise_for_status();pages=r.json().get("query",{}).get("pages",{})
  candidates=[]
  for page in pages.values():
   info=(page.get("imageinfo") or [{}])[0];mime=str(info.get("mime",""));url=info.get("thumburl") or info.get("url")
   if url and mime.startswith("image/") and mime not in {"image/svg+xml","image/gif"}:candidates.append(url)
  return _random.choice(candidates) if candidates else None
 except (httpx.HTTPError,ValueError):log.warning("IMAGE_LOOKUP_FAILED");return None
async def image_command(update,context):
 term=" ".join(context.args).strip()
 if not term:return await update.effective_message.reply_text("🖼️ Usage: /image <what you want to see>",reply_to_message_id=update.effective_message.message_id)
 url=await get_image_url(term)
 if not url:return await update.effective_message.reply_text("☾ I couldn't find a clean image for that.",reply_to_message_id=update.effective_message.message_id)
 try:await context.bot.send_photo(update.effective_chat.id,url,reply_to_message_id=update.effective_message.message_id)
 except Exception:log.exception("IMAGE_SEND_FAILED");await update.effective_message.reply_text("☾ The image couldn't be delivered this time.",reply_to_message_id=update.effective_message.message_id)
async def maybe_react_to_message(update,context):
 if not update.message or not chat_enabled.get(str(update.effective_chat.id),False) or _random.random()>0.08:return
 try:await context.bot.set_message_reaction(chat_id=update.effective_chat.id,message_id=update.message.message_id,reaction=_random.choice(REACTION_EMOJIS))
 except Exception:pass
async def send_text_with_gif(update,context,text,term=None):
 if update.message:await update.message.reply_text(text,reply_to_message_id=update.message.message_id)
 if term:
  url=await get_gif_url(term)
  if url:await context.bot.send_animation(update.effective_chat.id,url,reply_to_message_id=update.message.message_id if update.message else None)
async def send_mood_gif(update,context):return await send_random_gif(update,context)
async def gif_reply(update,context):return await send_random_gif(update,context)
async def sticker_reply(update,context):return await send_random_sticker(update,context)
