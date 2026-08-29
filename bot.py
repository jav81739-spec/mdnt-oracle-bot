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
from friend_engine import FriendEngine
from midnight_oracle.database import Database
from midnight_oracle.friend_engine import FriendEngine as Phase1FriendEngine, GroupContext as Phase1GroupContext
from midnight_oracle.memory_engine import MemoryEngine as Phase1MemoryEngine

# Never let a stale/retired Render environment resurrect a known-dead model.
if hasattr(legacy_bot,"GEMINI_MODEL"):
    configured=os.getenv("GEMINI_MODEL","").strip(); retired={"gemini-2.0-flash","gemini-3.7-flash","gemini-3.5-flash-lite"}
    legacy_bot.GEMINI_MODEL=configured if configured and configured not in retired else "gemini-3.6-flash"
    log.info("AI_MODEL_SELECTED | model=%s",legacy_bot.GEMINI_MODEL)

if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID

# ── Friend Engine: ambient social intelligence ────────────────────────────
_friend_engine=FriendEngine()
_friend_recent: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=8))
_friend_social_cooldown=float(os.getenv("ORACLE_SOCIAL_COOLDOWN_SECONDS", "1200"))
_phase1_db: Database | None = None
_phase1_engine: Phase1FriendEngine | None = None
_phase1_memory: Phase1MemoryEngine | None = None


def _is_direct_summon(update, text: str, bot_username: str = "") -> bool:
    """Return True when an existing explicit Telegram/Oracle trigger should bypass ambient social logic."""
    message=getattr(update,"effective_message",None) or getattr(update,"message",None)
    if not message:
        return False
    if getattr(message.chat,"type","") == "private": return True
    low=(text or "").casefold()
    if bot_username and f"@{bot_username.casefold()}" in low: return True
    if re.search(r"\b(?:midnight|oracle)\b", low): return True
    replied=getattr(message,"reply_to_message",None); replied_user=getattr(replied,"from_user",None)
    return bool(getattr(replied_user,"is_bot",False))


def _build_friend_context(update, text: str, bot_username: str = "") -> dict:
    """Build the bounded social context consumed by the compatibility FriendEngine."""
    message=getattr(update,"effective_message",None) or getattr(update,"message",None); chat=getattr(update,"effective_chat",None); user=getattr(update,"effective_user",None)
    chat_id=str(getattr(chat,"id",0)); now=datetime.now(ORACLE_TZ); recent=_friend_recent[chat_id]
    return {"sender":str(getattr(user,"id",0)),"sender_name":getattr(user,"first_name",None) or "friend","group_id":chat_id,"recent_messages":list(recent),"hour":now.hour,"is_late_night":now.hour>=23 or now.hour<3,"now":now.timestamp(),"social_cooldown_seconds":_friend_social_cooldown,"ambient_engagement_rate":0.30,"direct_summon":_is_direct_summon(update,text,bot_username),"bot_username":bot_username,"message_id":getattr(message,"message_id",0)}


async def _provider_fallback(first_name="friend", *args, **kwargs):
    """Provide an internal conversational response when the external legacy provider is unavailable."""
    name=(first_name or "friend").strip()[:60]
    return random.choice((f"{name}, I'm here. Keep going — what were you saying? 🌙",f"I'm listening, {name}. Pick it up from there. ☾",f"Hmm, {name}. Tell me the rest — I'm with you. 🌙"))
legacy_bot._get_fallback_reply=_provider_fallback

_original_ai_handler=getattr(legacy_bot,"handle_ai_message",None)
if _original_ai_handler is not None:
    async def _resilient_ai_handler(update, context):
        """Route ambient groups through the persistent Phase 1 Friend Engine and preserve explicit legacy behaviour."""
        message=getattr(update,"effective_message",None) or getattr(update,"message",None); text=(getattr(message,"text",None) or "").strip(); bot_username=""
        try: bot_username=await legacy_bot._get_bot_username(context.bot)
        except Exception: pass
        if message and text and not _is_direct_summon(update,text,bot_username) and getattr(message.chat,"type","") in {"group","supergroup"} and _phase1_engine is not None:
            try:
                uid=message.from_user.id if message.from_user else 0; gid=message.chat.id; now=datetime.now(ORACLE_TZ); recent=list(_friend_recent[str(gid)])
                tier="new"; memory_snippet="none"
                if _phase1_db:
                    row=await _phase1_db.fetchone("SELECT relationship_tier FROM members WHERE user_id=? AND group_id=?",(uid,gid)); tier=str(row[0]) if row else "new"
                    memories=await _phase1_db.memories(uid,gid,limit=3); memory_snippet=" | ".join(memories[:3])
                ctx=Phase1GroupContext(str(uid),str(gid),recent,now.hour,now.hour>=23 or now.hour<3,message.chat.title or "",tier,message.from_user.first_name if message.from_user else "friend",now.timestamp(),memory_snippet)
                decision=await _phase1_engine.process_message(message,ctx); _friend_recent[str(gid)].append(text)
                if decision.should_reply and decision.reply_text:
                    try: await context.bot.send_chat_action(chat_id=gid,action="typing")
                    except Exception: pass
                    await message.reply_text(decision.reply_text)
                    log.info("AUTONOMOUS_JOB_ENTERED | mode=ambient_friend | group=%s | sender=%s | reason=%s",gid,uid,decision.reason)
                    return
            except Exception: log.exception("PHASE1_FRIEND_ENGINE_FAILURE")
        try:
            return await _original_ai_handler(update, context)
        except Exception:
            user=getattr(update,"effective_user",None); name=getattr(user,"first_name",None) or "friend"
            log.exception("AI_PROVIDER_OR_HANDLER_FAILURE | local_chat_mode=engaged | user=%s",name)
            try:
                if message: await message.reply_text(await _provider_fallback(name)); log.info("AI_LOCAL_CHAT_SENT | user=%s",name)
            except Exception: log.exception("AI_LOCAL_CHAT_SEND_FAILED | user=%s",name)
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
    """Construct the production Telegram application without duplicate polling or legacy scheduler registration."""
    app=Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL,_registry),group=-999)
    try:
        from handlers.social_engine import track_member
        app.add_handler(MessageHandler(filters.ALL,track_member),group=-998)
    except Exception: log.exception("member tracker registration failed")
    if hasattr(legacy_bot,"register_handlers"): legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot,"_register_handlers"): legacy_bot._register_handlers(app)
    if not _has_ai_handler(app):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,_resilient_ai_handler),group=10); log.info("AI_HANDLER_GUARD_INSTALLED | direct_text_handler=true")
    try:
        from handlers.social_engine import init_storage
        init_storage(_storage_client)
        from handlers.member_memory import init
        app.bot_data["member_memory_init"]=init
    except Exception: log.exception("memory bootstrap wiring failed")
    try:
        from handlers import aesthetic
        for name in ("aura","identity","oracle","nightreport","shadow","element","vibecheck","corecode","universe","ritual","sigil","duality","glitch"):
            cb=getattr(aesthetic,f"{name}_command",None)
            if cb and name not in _command_names(app): app.add_handler(CommandHandler(name,cb))
    except Exception: log.exception("aesthetic registration failed")
    return app

DESCRIPTIONS={"start":"🌙 Enter the Midnight Realm","help":"📖 What Midnight Oracle can do","oracle":"🔮 Daily Oracle","aura":"🟣 Aura","vibecheck":"✨ Vibe check","identity":"🃏 Oracle archetype","shadow":"🌑 Shadow self","element":"🌌 Cosmic element","corecode":"🔱 Core words","universe":"🌌 Universe message","ritual":"🕯️ Ritual","duality":"☯️ Duality","nightreport":"🌙 Night report","sigil":"🔱 Personal sigil","glitch":"⚡ Oracle glitch","checkin":"🌙 Daily check-in","streakcheck":"📊 Streak","coinboard":"🏆 Coin leaderboard","cgift":"💝 Gift coins","rob":"🦹 Rob coins","vent":"🫀 Anonymous vent","announce":"📢 Owner announcement","broadcast":"📣 Owner broadcast","midnightmap":"🗺️ Midnight Map"}
OWNER={"announce","broadcast","midnightmap"}

async def _set_commands(app):
    """Publish the existing public and owner command menus to Telegram."""
    names=sorted([n for n in _command_names(app) if n and len(n)<=32])[:100]; public=[n for n in names if n not in OWNER]; make=lambda xs:[BotCommand(n,DESCRIPTIONS.get(n,"Midnight Oracle")) for n in xs]
    try:
        for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats(),BotCommandScopeAllChatAdministrators(),BotCommandScopeDefault()):
            await app.bot.delete_my_commands(scope=scope); await app.bot.set_my_commands(make(public),scope=scope)
        if OWNER_ID: await app.bot.set_my_commands(make(public+[n for n in names if n in OWNER]),scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception: log.exception("command menu setup failed")

async def _post_init(app):
    """Initialize production services exactly once after Telegram application startup."""
    global _phase1_db,_phase1_engine,_phase1_memory
    await _set_commands(app)
    try:
        _phase1_db=Database(os.getenv("ORACLE_DATABASE_PATH","midnight_oracle.sqlite3")); await _phase1_db.connect(); _phase1_memory=Phase1MemoryEngine(_phase1_db); _phase1_engine=Phase1FriendEngine(_phase1_db); log.info("PHASE1_FRIEND_ENGINE_READY | storage=sqlite | generation=openai")
    except Exception: log.exception("PHASE1_FRIEND_ENGINE_INIT_FAILED")
    try:
        from handlers.social_engine import init_storage
        init_storage(_storage_client)
        from handlers.member_memory import init
        await init(_storage_client)
    except Exception: log.exception("storage/memory init failed")
    try:
        from handlers.friend_engine import register
        register(app)
    except Exception: log.exception("FRIEND_ENGINE_REGISTRATION_FAILED")
    try:
        from handlers.presence_engine import register,silence_check
        register(app); app.job_queue.run_daily(silence_check,time=__import__('datetime').time(2,0,tzinfo=ORACLE_TZ),name="presence_silence_check")
    except Exception: log.exception("presence engine registration failed")
    log.info("AUTONOMOUS_CANONICAL_READY | legacy_social_scheduler=disabled | friend_engine=on | memory=on")
    log.info("AI_RUNTIME_READY | handler_guard=%s | model=%s",_has_ai_handler(app),getattr(legacy_bot,"GEMINI_MODEL","legacy-disabled"))
    log.info("Post-init complete — Midnight Oracle is ready")

def _error(update,context):
    """Log Telegram handler failures without leaking provider details to users."""
    log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)

def main():
    """Start the single production polling process."""
    app=build_application(); app.post_init=_post_init; app.add_error_handler(_error); log.info("Midnight Oracle starting — instance %s",startup._INSTANCE_ID); asyncio.run(startup.run(app,storage_client=_storage_client))

if __name__=="__main__": main()
