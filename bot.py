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
ORACLE_TZ=ZoneInfo(os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata"))
try:
    from storage import redis_client as _storage_client
except Exception:
    _storage_client=None
import startup; startup.init(_storage_client)
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PollAnswerHandler, PollHandler, InlineQueryHandler, filters
import legacy_bot
from midnight_oracle.database import Database
from midnight_oracle.friend_engine import FriendEngine as Phase1FriendEngine, GroupContext as Phase1GroupContext
from midnight_oracle.memory_engine import MemoryEngine as Phase1MemoryEngine
from midnight_oracle.mood_engine import MoodEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator
from midnight_oracle.handlers.message_handler import MessageRouter
from midnight_oracle.handlers.phase_registry import register_phase_surfaces

if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID
_friend_recent: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=8))
_phase1_db: Database | None = None
_phase1_engine: Phase1FriendEngine | None = None
_phase1_memory: Phase1MemoryEngine | None = None
_phase1_replies: ReplyGenerator | None = None

def _is_direct_summon(update, text: str, bot_username: str = "") -> bool:
    message=getattr(update,"effective_message",None) or getattr(update,"message",None)
    if not message:return False
    if getattr(message.chat,"type","")=="private":return True
    low=(text or "").casefold()
    if bot_username and f"@{bot_username.casefold()}" in low:return True
    return bool(re.search(r"\b(oracle|midnight)\b",low))

def _command_names(app):
    names=set()
    for handlers in getattr(app,"handlers",{}).values():
        for handler in handlers:
            for command in (getattr(handler,"commands",None) or ()):
                value=str(command).strip().lstrip("/").casefold()
                if value:names.add(value)
    return names

def build_application():
    app=Application.builder().token(TOKEN).build()
    app.bot_data["storage_client"]=_storage_client
    register_phase_surfaces(app)
    try:
        from handlers import relationship_engine
        relationship_engine.register(app)
    except Exception:log.exception("RELATIONSHIP_SURFACE_REGISTRATION_FAILED")
    async def _refresh_group_command_scope(update, context):
        chat=getattr(update,"effective_chat",None)
        if not chat or getattr(chat,"type","") not in ("group","supergroup"): return
        chat_id=int(chat.id)
        refreshed=app.bot_data.setdefault("_command_scope_refreshed",set())
        if chat_id in refreshed:return
        commands=app.bot_data.get("public_command_commands") or []
        if not commands:return
        try:
            await startup.register_chat(chat_id,chat.type,getattr(chat,"title","") or "")
            await app.bot.set_my_commands(commands,scope=BotCommandScopeChat(chat_id))
            refreshed.add(chat_id)
            log.info("COMMAND_MENU_GROUP_SCOPE_REFRESHED | count=%d",len(commands))
        except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")
    app.add_handler(MessageHandler(filters.ChatType.GROUPS,_refresh_group_command_scope),group=-998)
    return app

async def _set_commands(app):
    private={"ownerstatus","ownerstats"}
    names=sorted(n for n in _command_names(app) if n and len(n)<=32 and n not in private)[:100]
    descriptions={"start":"Midnight Oracle","help":"Command guide","oracle":"Daily prophecy","aura":"Scan your aura","vibecheck":"Check your energy","identity":"Oracle archetype","shadow":"Meet your shadow","element":"Cosmic element","corecode":"Three core words","universe":"A message from the universe","ritual":"Today's ritual","duality":"Light and dark side","nightreport":"Tonight's night report","sigil":"Personal sigil","glitch":"Oracle system reading","checkin":"Daily check-in","streakcheck":"View your streak","vent":"Private vent","coinboard":"Group coin leaderboard","cgift":"Gift coins","rob":"Attempt a heist","tod":"Truth or Dare","wyr":"Would You Rather","nhie":"Never Have I Ever","scramble":"Word Scramble","predict":"Make a prediction","predictions":"Pending predictions","house":"Open Oracle House","truth":"Truth question","memory":"Group memory","mymemory":"What Oracle remembers","forget":"Forget a memory","quiet":"Quiet mode","wake":"Wake Oracle","weave":"Reveal a social thread","orbit":"Trace a social orbit","echo":"Find an echo","anchor":"Read an anchor","fracture":"Read a fracture","ember":"Find an ember","mirror":"Mirror reading","crossing":"Read a crossing","undertow":"Read the undertow","edict":"Oracle edict","veil":"Check the sealed veil","gaze":"Watch a relationship","release":"Release a relationship watch","graveyard":"The Quiet Graveyard"}
    commands=[BotCommand(n,descriptions.get(n,"Midnight Oracle")) for n in names]
    app.bot_data["public_command_commands"]=commands
    scopes=(("private",BotCommandScopeAllPrivateChats()),("groups",BotCommandScopeAllGroupChats()),("default",None))
    for label,scope in scopes:
        try:
            if scope is None: await app.bot.set_my_commands(commands)
            else: await app.bot.set_my_commands(commands,scope=scope)
            log.info("COMMAND_MENU_PUBLISHED | scope=%s | count=%d",label,len(commands))
        except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED | scope=%s",label)
    try:
        registry=await startup.get_chat_registry()
        for chat_id,info in registry.items():
            if info.get("type") in ("group","supergroup"):
                try:
                    await app.bot.set_my_commands(commands,scope=BotCommandScopeChat(int(chat_id)))
                    log.info("COMMAND_MENU_GROUP_OVERRIDE_REFRESHED | count=%d",len(commands))
                except Exception:log.exception("COMMAND_MENU_GROUP_OVERRIDE_REFRESH_FAILED")
    except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")
    try:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        log.info("COMMAND_MENU_BUTTON_READY | menu=commands")
    except Exception:log.exception("COMMAND_MENU_BUTTON_FAILED")
    if OWNER_ID:
        try:
            owner_names=sorted(n for n in _command_names(app) if n in private)
            owner_menu=list(commands)
            seen={c.command for c in owner_menu}
            for n in owner_names:
                if n not in seen and len(owner_menu)<100:
                    owner_menu.append(BotCommand(n,"Private Oracle control"));seen.add(n)
            await app.bot.set_my_commands(owner_menu,scope=BotCommandScopeChat(OWNER_ID))
            log.info("COMMAND_MENU_OWNER_REFRESHED | member=%d | owner=%d",len(commands),len(owner_names))
        except Exception:log.exception("owner command menu setup failed")

async def _post_init(app):
    global _phase1_db,_phase1_engine,_phase1_memory,_phase1_replies
    try:
        _phase1_db=Database(os.getenv("ORACLE_DATABASE_PATH","midnight_oracle.sqlite3"));await _phase1_db.connect();_phase1_memory=Phase1MemoryEngine(_phase1_db);_phase1_engine=Phase1FriendEngine(_phase1_db);_phase1_replies=ReplyGenerator();app.bot_data["oracle_db"]=_phase1_db;app.bot_data["oracle_router"]=MessageRouter(_phase1_engine,_phase1_memory,MoodEngine(),_phase1_replies)
        from midnight_oracle.scheduler import OracleScheduler
        oracle_scheduler=OracleScheduler(app,_phase1_db,ORACLE_TZ);oracle_scheduler.start();app.bot_data["oracle_scheduler"]=oracle_scheduler;log.info("PHASE1_FRIEND_ENGINE_READY | storage=sqlite | generation=openai");log.info("PHASE2_5_SURFACE_READY | scheduler=on | games=on | secret_events=on | mini_app=on")
    except Exception:log.exception("PHASE1_FRIEND_ENGINE_INIT_FAILED")
    try:
        from handlers.friend_engine import register
        register(app)
    except Exception:log.exception("FRIEND_ENGINE_REGISTRATION_FAILED")
    try:
        from handlers.owner_console_v2 import register as register_owner
        register_owner(app)
    except Exception:log.exception("OWNER_CONSOLE_REGISTRATION_FAILED")
    try:
        from handlers.memorial import register as register_memorial
        register_memorial(app)
    except Exception:log.exception("MEMORIAL_SURFACE_REGISTRATION_FAILED")
    await _set_commands(app);log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on | social=on | world=on")

def _error(update,context):log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)
def main():
    app=build_application();app.post_init=_post_init;app.add_error_handler(_error);asyncio.run(startup.run(app,storage_client=_storage_client))
if __name__=="__main__":main()
