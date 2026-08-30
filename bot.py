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

ADMIN_ONLY_COMMANDS={
    "broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload",
    "shutdown","restart","admin","moderation","mute","unmute","ban","kick","warn","clearwarns",
    "pin","unpin","purge","setrules","lock","unlock","groupinfo","setwelcome","setgoodbye",
}

if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID

def _command_names(app):
    names=set()
    for handlers in getattr(app,"handlers",{}).values():
        for handler in handlers:
            for command in (getattr(handler,"commands",None) or ()):
                value=str(command).strip().lstrip("/").casefold()
                if value:names.add(value)
    return names

def _ensure_member_help(app):
    """Make the premium member /help and /start handlers part of this live entrypoint."""
    existing=_command_names(app)
    try:
        from handlers.help_command import help_command, start_command
        if "help" not in existing: app.add_handler(CommandHandler("help",help_command),group=-1)
        if "start" not in existing: app.add_handler(CommandHandler("start",start_command),group=-1)
    except Exception: log.exception("MEMBER_HELP_REGISTRATION_FAILED")

def build_application():
    app=Application.builder().token(TOKEN).build()
    app.bot_data["storage_client"]=_storage_client
    register_phase_surfaces(app)
    _ensure_member_help(app)
    try:
        from handlers import relationship_engine
        relationship_engine.register(app)
    except Exception:log.exception("RELATIONSHIP_SURFACE_REGISTRATION_FAILED")

    async def _refresh_group_command_scope(update, context):
        chat=getattr(update,"effective_chat",None)
        if not chat or getattr(chat,"type","") not in ("group","supergroup"): return
        chat_id=int(chat.id);refreshed=app.bot_data.setdefault("_command_scope_refreshed",set())
        if chat_id in refreshed:return
        commands=app.bot_data.get("public_command_commands") or []
        if not commands:return
        try:
            await startup.register_chat(chat_id,chat.type,getattr(chat,"title","") or "")
            await app.bot.set_my_commands(commands,scope=BotCommandScopeChat(chat_id));refreshed.add(chat_id)
            log.info("COMMAND_MENU_GROUP_SCOPE_REFRESHED | count=%d",len(commands))
        except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")

    # Human chat and autonomous social tracking are installed by startup.run()
    # after post_init, so the production runtime has exactly one owner for each
    # surface and cannot double-answer or double-count a message.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS,_refresh_group_command_scope),group=-1000)
    log.info("LIVE_RUNTIME_BRIDGES_DEFERRED_TO_STARTUP | chat=canonical | social=canonical")
    return app

async def _set_commands(app):
    _ensure_member_help(app)
    names=sorted(n for n in _command_names(app) if n and len(n)<=32 and n not in ADMIN_ONLY_COMMANDS)
    try:
        from handlers.help_command import SECTIONS, HINTS
        priority=[name for _,commands in SECTIONS for name in commands]
    except Exception:
        priority=[];HINTS={}
    priority=["start","help"]+priority;rank={name:index for index,name in enumerate(priority)}
    ordered=sorted(names,key=lambda name:(rank.get(name,10_000),name));visible=ordered[:100]
    commands=[BotCommand(name,HINTS.get(name,"Midnight Oracle")) for name in visible]
    app.bot_data["public_command_commands"]=commands;app.bot_data["public_command_names"]=names
    scopes=(("private",BotCommandScopeAllPrivateChats()),("groups",BotCommandScopeAllGroupChats()),("default",None))
    for label,scope in scopes:
        try:
            if scope is None: await app.bot.set_my_commands(commands)
            else: await app.bot.set_my_commands(commands,scope=scope)
            log.info("COMMAND_MENU_PUBLISHED | scope=%s | count=%d | total_live=%d",label,len(commands),len(names))
        except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED | scope=%s",label)
    try:
        registry=await startup.get_chat_registry()
        for chat_id,info in registry.items():
            if info.get("type") in ("group","supergroup"):
                try: await app.bot.set_my_commands(commands,scope=BotCommandScopeChat(int(chat_id)));log.info("COMMAND_MENU_GROUP_OVERRIDE_REFRESHED | count=%d",len(commands))
                except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")
    except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")
    try: await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands());log.info("COMMAND_MENU_BUTTON_READY | menu=commands")
    except Exception:log.exception("COMMAND_MENU_BUTTON_FAILED")
    if OWNER_ID:
        try:
            owner_names=sorted(n for n in _command_names(app) if n in {"ownerstatus","ownerstats"});owner_menu=list(commands);seen={c.command for c in owner_menu}
            for n in owner_names:
                if n not in seen and len(owner_menu)<100:owner_menu.append(BotCommand(n,"Private Oracle control"));seen.add(n)
            await app.bot.set_my_commands(owner_menu,scope=BotCommandScopeChat(OWNER_ID));log.info("COMMAND_MENU_OWNER_REFRESHED | member=%d | owner=%d",len(commands),len(owner_names))
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
    _ensure_member_help(app);await _set_commands(app);log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on | social=on | world=on")

_phase1_db: Database | None = None
_phase1_engine: Phase1FriendEngine | None = None
_phase1_memory: Phase1MemoryEngine | None = None
_phase1_replies: ReplyGenerator | None = None

def _error(update,context):log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)
def main():
    app=build_application();app.post_init=_post_init;app.add_error_handler(_error);asyncio.run(startup.run(app,storage_client=_storage_client))
if __name__=="__main__":main()
