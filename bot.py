"""Midnight Oracle — single production entrypoint."""
from __future__ import annotations
import asyncio, logging, os, sys, random, re
from collections import defaultdict, deque
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
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PollAnswerHandler, PollHandler, InlineQueryHandler, filters
import legacy_bot
from midnight_oracle.database import Database
from midnight_oracle.friend_engine import FriendEngine as Phase1FriendEngine
from midnight_oracle.memory_engine import MemoryEngine as Phase1MemoryEngine
from midnight_oracle.mood_engine import MoodEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator
from midnight_oracle.handlers.message_handler import MessageRouter
from midnight_oracle.handlers.phase_registry import register_phase_surfaces

ADMIN_ONLY_COMMANDS={"broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload","shutdown","restart","admin","moderation","mute","unmute","ban","kick","warn","clearwarns","pin","unpin","purge","setrules","lock","unlock","groupinfo","setwelcome","setgoodbye"}
if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID
_phase1_db: Database | None = None
_phase1_engine: Phase1FriendEngine | None = None
_phase1_memory: Phase1MemoryEngine | None = None
_phase1_replies: ReplyGenerator | None = None

def _command_names(app):
    names=set()
    for handlers in getattr(app,"handlers",{}).values():
        for handler in handlers:
            for command in (getattr(handler,"commands",None) or ()):
                value=str(command).strip().lstrip("/").casefold()
                if value:names.add(value)
    return names

def _ensure_member_help(app):
    existing=_command_names(app)
    try:
        from handlers.help_command import help_command, start_command
        if "help" not in existing: app.add_handler(CommandHandler("help",help_command),group=-1)
        if "start" not in existing: app.add_handler(CommandHandler("start",start_command),group=-1)
    except Exception: log.exception("MEMBER_HELP_REGISTRATION_FAILED")

def build_application():
    app=Application.builder().token(TOKEN).build();app.bot_data["storage_client"]=_storage_client
    register_phase_surfaces(app);_ensure_member_help(app)
    try:
        from handlers import relationship_engine; relationship_engine.register(app)
    except Exception:log.exception("RELATIONSHIP_SURFACE_REGISTRATION_FAILED")
    async def _refresh_group_command_scope(update,context):
        chat=getattr(update,"effective_chat",None)
        if not chat or getattr(chat,"type","") not in ("group","supergroup"):return
        refreshed=app.bot_data.setdefault("_command_scope_refreshed",set());chat_id=int(chat.id)
        if chat_id in refreshed:return
        commands=app.bot_data.get("public_command_commands") or []
        if not commands:return
        try:
            await startup.register_chat(chat_id,chat.type,getattr(chat,"title","") or "");await app.bot.set_my_commands(commands,scope=BotCommandScopeChat(chat_id));refreshed.add(chat_id)
        except Exception:log.exception("COMMAND_MENU_GROUP_SCOPE_REFRESH_FAILED")
    async def _live_human_chat(update,context):
        message=getattr(update,"effective_message",None);chat=getattr(update,"effective_chat",None);user=getattr(update,"effective_user",None)
        if not message or not chat or not user or user.is_bot:return
        text=(message.text or message.caption or "").strip()
        if not text or text.startswith("/"):return
        router=app.bot_data.get("oracle_router")
        if router is None:return
        try:await router.handle(update,context)
        except Exception:log.exception("LIVE_CHAT_ROUTER_FAILED | chat=%s | user=%s",chat.id,user.id)
    async def _track_social_member(update,context):
        message=getattr(update,"effective_message",None);chat=getattr(update,"effective_chat",None);user=getattr(update,"effective_user",None)
        if not message or not chat or not user or user.is_bot or chat.type not in ("group","supergroup"):return
        try:
            from handlers import social_engine;await social_engine.register_member(chat.id,user.id,user.first_name or "friend",user.username or "");await social_engine.bump_msg_count(chat.id,user.id)
        except Exception:log.exception("SOCIAL_MEMBER_TRACK_FAILED | chat=%s | user=%s",chat.id,user.id)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS,_refresh_group_command_scope),group=-1000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,_live_human_chat),group=-900)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,_track_social_member),group=-899)
    return app

async def _set_commands(app):
    _ensure_member_help(app);names=sorted(n for n in _command_names(app) if n and len(n)<=32 and n not in ADMIN_ONLY_COMMANDS)
    try:
        from handlers.help_command import SECTIONS,HINTS;priority=[name for _,commands in SECTIONS for name in commands]
    except Exception:priority=[];HINTS={}
    rank={name:index for index,name in enumerate(["start","help"]+priority)};ordered=sorted(names,key=lambda n:(rank.get(n,10000),n));commands=[BotCommand(n,HINTS.get(n,"Midnight Oracle")) for n in ordered[:100]]
    app.bot_data["public_command_commands"]=commands;app.bot_data["public_command_names"]=names
    for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats()):
        try:await app.bot.set_my_commands(commands,scope=scope)
        except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED")
    try:await app.bot.set_my_commands(commands)
    except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED | scope=default")
    try:await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:log.exception("COMMAND_MENU_BUTTON_FAILED")

async def _post_init(app):
    global _phase1_db,_phase1_engine,_phase1_memory,_phase1_replies
    try:
        _phase1_db=Database(os.getenv("ORACLE_DATABASE_PATH","midnight_oracle.sqlite3"));await _phase1_db.connect();_phase1_memory=Phase1MemoryEngine(_phase1_db);_phase1_engine=Phase1FriendEngine(_phase1_db);_phase1_replies=ReplyGenerator();app.bot_data["oracle_db"]=_phase1_db;app.bot_data["oracle_router"]=MessageRouter(_phase1_engine,_phase1_memory,MoodEngine(),_phase1_replies)
        from midnight_oracle.scheduler import OracleScheduler;oracle_scheduler=OracleScheduler(app,_phase1_db,ORACLE_TZ);oracle_scheduler.start();app.bot_data["oracle_scheduler"]=oracle_scheduler
    except Exception:log.exception("PHASE1_FRIEND_ENGINE_INIT_FAILED")
    for module,fn in (("handlers.friend_engine","register"),("handlers.owner_console_v2","register"),("handlers.memorial","register")):
        try:
            mod=__import__(module,fromlist=[fn]);getattr(mod,fn)(app)
        except Exception:log.exception("SURFACE_REGISTRATION_FAILED | %s",module)
    _ensure_member_help(app);await _set_commands(app);log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on | social=on | world=on")

def _error(update,context):log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)

def _enable_all_update_types(app):
    original=app.updater.start_polling
    async def start_polling(*args,**kwargs):
        kwargs["allowed_updates"]=Update.ALL_TYPES
        return await original(*args,**kwargs)
    app.updater.start_polling=start_polling

def main():
    app=build_application();_enable_all_update_types(app);app.post_init=_post_init;app.add_error_handler(_error);asyncio.run(startup.run(app,storage_client=_storage_client))
if __name__=="__main__":main()
