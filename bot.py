"""Midnight Oracle — single production entrypoint."""
from __future__ import annotations
import asyncio, logging, os, sys, random, re
from collections import defaultdict, deque
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",level=logging.INFO)
log=logging.getLogger("midnight.bot")
TOKEN=os.getenv("BOT_TOKEN","").strip()
if not TOKEN: log.critical("BOT_TOKEN is not set"); sys.exit(1)
GROUP_CHAT_ID=int(os.getenv("GROUP_CHAT_ID","0") or "0"); OWNER_ID=int(os.getenv("OWNER_ID","0") or "0")
ORACLE_TZ=ZoneInfo(os.getenv("ORACLE_TIMEZONE","Asia/Kolkata"))
try:
    from storage import redis_client as _storage_client
except Exception: _storage_client=None
import startup; startup.init(_storage_client)
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import legacy_bot
from midnight_oracle.friend_engine import FriendEngine
from midnight_oracle.database import Database
from midnight_oracle.friend_engine import FriendEngine as Phase1FriendEngine, GroupContext as Phase1GroupContext
from midnight_oracle.memory_engine import MemoryEngine as Phase1MemoryEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator

if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID

_friend_recent: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=8))
_phase1_db: Database | None = None
_phase1_engine: Phase1FriendEngine | None = None
_phase1_memory: Phase1MemoryEngine | None = None
_phase1_replies: ReplyGenerator | None = None


def _is_direct_summon(update, text: str, bot_username: str = "") -> bool:
    """Return True when an explicit Telegram/Oracle trigger should bypass ambient social scoring."""
    message=getattr(update,"effective_message",None) or getattr(update,"message",None)
    if not message: return False
    if getattr(message.chat,"type","") == "private": return True
    low=(text or "").casefold()
    if bot_username and f"@{bot_username.casefold()}" in low: return True
    if re.search(r"\b(?:midnight|oracle)\b", low): return True
    replied=getattr(message,"reply_to_message",None); replied_user=getattr(replied,"from_user",None)
    return bool(getattr(replied_user,"is_bot",False))


async def _phase1_direct_reply(update, context, text: str, bot_username: str) -> bool:
    """Generate a direct or private reply through the configured reply generator."""
    if _phase1_replies is None: return False
    message=getattr(update,"effective_message",None); user=getattr(update,"effective_user",None); chat=getattr(update,"effective_chat",None)
    if not message or not user or not chat: return False
    now=datetime.now(ORACLE_TZ); gid=chat.id; tier="new"; memory_snippet="none"
    if _phase1_db and chat.type in {"group","supergroup"}:
        row=await _phase1_db.fetchone("SELECT relationship_tier FROM members WHERE user_id=? AND group_id=?",(user.id,gid)); tier=str(row[0]) if row else "new"
        memories=await _phase1_db.memories(user.id,gid,limit=3); memory_snippet=" | ".join(memories[:3])
    try: await context.bot.send_chat_action(chat_id=gid,action="typing")
    except Exception: pass
    reply=await _phase1_replies.generate(chat.title or "Midnight Oracle",user.first_name or "friend",tier,text,_phase1_engine.mood.group_mood(gid).summary() if _phase1_engine and chat.type in {"group","supergroup"} else "private conversation",str(now.hour),now.hour>=23 or now.hour<3,memory_snippet)
    await message.reply_text(reply); return True


async def _resilient_ai_handler(update, context):
    """Own the complete text decision path: direct/private reply or ambient FriendEngine, otherwise silence."""
    message=getattr(update,"effective_message",None) or getattr(update,"message",None); text=(getattr(message,"text",None) or "").strip(); bot_username=""
    if not message or not text or text.startswith("/"): return
    try: bot_username=await legacy_bot._get_bot_username(context.bot)
    except Exception: pass
    direct=_is_direct_summon(update,text,bot_username); chat_type=getattr(message.chat,"type","")
    if direct or chat_type == "private":
        try:
            if await _phase1_direct_reply(update,context,text,bot_username): return
        except Exception: log.exception("OPENAI_DIRECT_REPLY_FAILURE")
        return
    if chat_type not in {"group","supergroup"} or _phase1_engine is None: return
    try:
        uid=message.from_user.id if message.from_user else 0; gid=message.chat.id; now=datetime.now(ORACLE_TZ); recent=list(_friend_recent[str(gid)]); tier="new"; memory_snippet="none"
        if _phase1_db:
            row=await _phase1_db.fetchone("SELECT relationship_tier,interaction_count FROM members WHERE user_id=? AND group_id=?",(uid,gid)); tier=str(row[0]) if row else "new"
            memories=await _phase1_db.memories(uid,gid,limit=3); memory_snippet=" | ".join(memories[:3]); await _phase1_db.upsert_member(uid,gid,getattr(message.from_user,"username","") or "",getattr(message.from_user,"first_name","") or "friend")
        ctx=Phase1GroupContext(str(uid),str(gid),recent,now.hour,now.hour>=23 or now.hour<3,message.chat.title or "",tier,message.from_user.first_name if message.from_user else "friend",now.timestamp(),memory_snippet)
        decision=await _phase1_engine.process_message(message,ctx); _friend_recent[str(gid)].append(text)
        if _phase1_memory and message.from_user: await _phase1_memory.observe(uid,gid,message.from_user.first_name or "friend",text,decision.should_reply)
        if decision.should_reply and decision.reply_text:
            try: await context.bot.send_chat_action(chat_id=gid,action="typing")
            except Exception: pass
            await message.reply_text(decision.reply_text); log.info("AUTONOMOUS_JOB_ENTERED | mode=ambient_friend | group=%s | sender=%s | reason=%s",gid,uid,decision.reason)
        else: log.info("AUTONOMOUS_JOB_SKIPPED | group=%s | sender=%s | reason=%s",gid,uid,decision.reason)
    except Exception: log.exception("PHASE1_FRIEND_ENGINE_FAILURE | ambient_silence=true")

legacy_bot.handle_ai_message=_resilient_ai_handler


async def _registry(update,context):
    """Record chat/member activity without changing command behaviour."""
    chat=getattr(update,"effective_chat",None)
    if chat and chat.type in ("group","supergroup","channel"):
        try: await startup.register_chat(chat.id,chat.type,chat.title or "")
        except Exception: log.debug("chat registration skipped",exc_info=True)
    user=getattr(update,"effective_user",None); msg=getattr(update,"effective_message",None)
    if user and chat and msg and getattr(msg,"text",None):
        try:
            from handlers.member_memory import remember
            await remember(chat.id,user.id,user.first_name or "friend",user.username or "",msg.text)
        except Exception: log.debug("member memory update skipped",exc_info=True)

def _command_names(app):
    """Return command names already registered on the application."""
    out=set()
    for hs in getattr(app,"handlers",{}).values():
        for h in hs:
            cs=getattr(h,"commands",None)
            if cs: out.update(str(c).lower().lstrip("/") for c in cs)
    return out

def _has_ai_handler(app):
    """Return whether the application contains the protected AI handler."""
    for hs in getattr(app,"handlers",{}).values():
        for h in hs:
            cb=getattr(h,"callback",None)
            if cb is _resilient_ai_handler or getattr(cb,"__name__","") in {"handle_ai_message","_resilient_ai_handler"}: return True
    return False

def build_application():
    """Construct the production Telegram application without duplicate polling or AI schedulers."""
    app=Application.builder().token(TOKEN).build(); app.add_handler(MessageHandler(filters.ALL,_registry),group=-999)
    try:
        from handlers.social_engine import track_member
        app.add_handler(MessageHandler(filters.ALL,track_member),group=-998)
    except Exception: log.exception("member tracker registration failed")
    if hasattr(legacy_bot,"register_handlers"): legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot,"_register_handlers"): legacy_bot._register_handlers(app)
    if not _has_ai_handler(app): app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,_resilient_ai_handler),group=10)
    return app

async def _set_commands(app):
    """Publish the existing command menus to Telegram."""
    names=sorted([n for n in _command_names(app) if n and len(n)<=32])[:100]
    commands=[BotCommand(n,"Midnight Oracle") for n in names]
    try: await app.bot.set_my_commands(commands)
    except Exception: log.exception("command menu setup failed")

async def _post_init(app):
    """Initialize production services exactly once after Telegram application startup."""
    global _phase1_db,_phase1_engine,_phase1_memory,_phase1_replies
    await _set_commands(app)
    try:
        _phase1_db=Database(os.getenv("ORACLE_DATABASE_PATH","midnight_oracle.sqlite3")); await _phase1_db.connect()
        _phase1_memory=Phase1MemoryEngine(_phase1_db); _phase1_engine=Phase1FriendEngine(_phase1_db); _phase1_replies=ReplyGenerator()
        log.info("PHASE1_FRIEND_ENGINE_READY | storage=sqlite | generation=openai")
    except Exception: log.exception("PHASE1_FRIEND_ENGINE_INIT_FAILED")
    try:
        from handlers.friend_engine import register
        register(app)
    except Exception: log.exception("FRIEND_ENGINE_REGISTRATION_FAILED")
    log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on")

def _error(update,context):
    """Log Telegram handler failures without leaking provider details to users."""
    log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)

def main():
    """Start the single production polling process."""
    app=build_application(); app.post_init=_post_init; app.add_error_handler(_error); log.info("Midnight Oracle starting — instance %s",startup._INSTANCE_ID); asyncio.run(startup.run(app,storage_client=_storage_client))

if __name__=="__main__": main()
