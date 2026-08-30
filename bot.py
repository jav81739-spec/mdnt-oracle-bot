"""Midnight Oracle — single production entrypoint."""
from __future__ import annotations
import asyncio,logging,os,sys
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv();logging.basicConfig(format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",level=logging.INFO);log=logging.getLogger("midnight.bot")
TOKEN=os.getenv("BOT_TOKEN","").strip()
if not TOKEN:log.critical("BOT_TOKEN is not set");sys.exit(1)
GROUP_CHAT_ID=int(os.getenv("GROUP_CHAT_ID","0") or "0");OWNER_ID=int(os.getenv("OWNER_ID","0") or "0");ORACLE_TZ=ZoneInfo(os.getenv("ORACLE_TIMEZONE","Asia/Kolkata"))
try:from storage import redis_client as _storage_client
except Exception:_storage_client=None
import startup;startup.init(_storage_client)
from telegram import BotCommand,BotCommandScopeAllGroupChats,BotCommandScopeAllPrivateChats,MenuButtonCommands
from telegram.ext import Application,CommandHandler
import legacy_bot
from midnight_oracle.database import Database
from midnight_oracle.friend_engine import FriendEngine as Phase1FriendEngine
from midnight_oracle.memory_engine import MemoryEngine as Phase1MemoryEngine
from midnight_oracle.mood_engine import MoodEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator
from midnight_oracle.handlers.message_handler import MessageRouter
from midnight_oracle.handlers.phase_registry import register_phase_surfaces
ADMIN_ONLY_COMMANDS={"broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload","shutdown","restart","admin","moderation","mute","unmute","ban","kick","warn","clearwarns","pin","unpin","purge","setrules","lock","unlock","groupinfo","setwelcome","setgoodbye"}
_phase1_db=None;_phase1_engine=None;_phase1_memory=None;_phase1_replies=None

def _command_names(app):return {str(c).strip().lstrip("/").casefold() for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
def _ensure_member_help(app):
    existing=_command_names(app)
    try:
        from handlers.help_command import help_command,start_command
        if "help" not in existing:app.add_handler(CommandHandler("help",help_command),group=-1)
        if "start" not in existing:app.add_handler(CommandHandler("start",start_command),group=-1)
    except Exception:log.exception("MEMBER_HELP_REGISTRATION_FAILED")

def build_application():
    app=Application.builder().token(TOKEN).build();app.bot_data["storage_client"]=_storage_client;register_phase_surfaces(app);_ensure_member_help(app)
    try:
        from handlers.legacy_surface import register_legacy_surface
        result=register_legacy_surface(app);log.info("LEGACY_SURFACE_WIRED | added=%d | skipped=%d",len(result.get("added",[])),len(result.get("skipped",[])))
    except Exception:log.exception("LEGACY_SURFACE_REGISTRATION_FAILED")
    try:
        from handlers.relationship_engine import register
        register(app)
    except Exception:log.exception("RELATIONSHIP_SURFACE_REGISTRATION_FAILED")
    return app

async def _post_init(app):
    global _phase1_db,_phase1_engine,_phase1_memory,_phase1_replies
    _phase1_db=Database(os.getenv("ORACLE_DATABASE_PATH","midnight_oracle.sqlite3"));await _phase1_db.connect();_phase1_memory=Phase1MemoryEngine(_phase1_db);_phase1_engine=Phase1FriendEngine(_phase1_db);_phase1_replies=ReplyGenerator();app.bot_data.update(oracle_db=_phase1_db,oracle_router=MessageRouter(_phase1_engine,_phase1_memory,MoodEngine(),_phase1_replies))
    from midnight_oracle.scheduler import OracleScheduler
    oracle_scheduler=OracleScheduler(app,_phase1_db,ORACLE_TZ);oracle_scheduler.start();app.bot_data["oracle_scheduler"]=oracle_scheduler
    try:
        from handlers import social_engine
        if not app.bot_data.get("_midnight_social_jobs_registered"):
            social_engine.init_storage(_storage_client);social_engine.register_jobs(app);app.bot_data["_midnight_social_jobs_registered"]=True
    except Exception:log.exception("SOCIAL_ENGINE_START_FAILED")
    for module,fn in (("handlers.friend_engine","register"),("handlers.owner_console_v2","register"),("handlers.memorial","register")):
        try:getattr(__import__(module,fromlist=[fn]),fn)(app)
        except Exception:log.exception("SURFACE_REGISTRATION_FAILED | %s",module)
    _ensure_member_help(app);await _set_commands(app)
    log.info("AUTONOMOUS_CANONICAL_READY | phase1_5=on | v2_surface=on | scheduler=on | social=on | world=on")

async def _set_commands(app):
    _ensure_member_help(app);names=sorted(n for n in _command_names(app) if n and len(n)<=32 and n not in ADMIN_ONLY_COMMANDS)
    try:
        from handlers.help_command import SECTIONS,HINTS
        priority=[name for _,commands in SECTIONS for name in commands]
    except Exception:priority=[];HINTS={}
    rank={name:i for i,name in enumerate(["start","help"]+priority)};ordered=sorted(names,key=lambda n:(rank.get(n,10000),n));commands=[BotCommand(n,HINTS.get(n,"Midnight Oracle")) for n in ordered[:100]];app.bot_data["public_command_commands"]=commands;app.bot_data["public_command_names"]=names
    for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats()):
        try:await app.bot.set_my_commands(commands,scope=scope)
        except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED")
    try:await app.bot.set_my_commands(commands)
    except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED | default")
    try:await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:log.exception("COMMAND_MENU_BUTTON_FAILED")

def _error(update,context):log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)
def main():
    app=build_application();app.post_init=_post_init;app.add_error_handler(_error);asyncio.run(startup.run(app,storage_client=_storage_client))
if __name__=="__main__":main()
