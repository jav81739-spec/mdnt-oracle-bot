"""Midnight Oracle — single production entrypoint."""
from __future__ import annotations
import asyncio, logging, os, sys
from datetime import time
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
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import legacy_bot
if hasattr(legacy_bot,"GEMINI_MODEL"):
    configured=os.getenv("GEMINI_MODEL","").strip(); retired={"gemini-2.0-flash","gemini-3.7-flash","gemini-3.5-flash-lite"}
    legacy_bot.GEMINI_MODEL=configured if configured and configured not in retired else "gemini-3.6-flash"
    log.info("AI_MODEL_SELECTED | model=%s",legacy_bot.GEMINI_MODEL)
if hasattr(legacy_bot,"GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID==0: legacy_bot.GROUP_CHAT_ID=GROUP_CHAT_ID
async def _registry(update,context):
    chat=getattr(update,"effective_chat",None)
    if chat and chat.type in ("group","supergroup","channel"): await startup.register_chat(chat.id,chat.type,chat.title or "")
def _command_names(app):
    out=set()
    for hs in getattr(app,"handlers",{}).values():
        for h in hs:
            cs=getattr(h,"commands",None)
            if cs: out.update(str(c).lower().lstrip("/") for c in cs)
    return out
def build_application():
    app=Application.builder().token(TOKEN).build(); app.add_handler(MessageHandler(filters.ALL,_registry),group=-999)
    try:
        from handlers.social_engine import track_member
        app.add_handler(MessageHandler(filters.ALL,track_member),group=-998)
    except Exception: log.exception("member tracker registration failed")
    if hasattr(legacy_bot,"register_handlers"): legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot,"_register_handlers"): legacy_bot._register_handlers(app)
    try:
        from handlers import aesthetic
        for name in ("aura","identity","oracle","nightreport","shadow","element","vibecheck","corecode","universe","ritual","sigil","duality","glitch"):
            cb=getattr(aesthetic,f"{name}_command",None)
            if cb and name not in _command_names(app): app.add_handler(CommandHandler(name,cb))
    except Exception: log.exception("aesthetic registration failed")
    return app
DESCRIPTIONS={"start":"🌙 Enter the Midnight Realm","help":"📖 What Midnight Oracle can do","oracle":"🔮 Daily Oracle","aura":"🟣 Aura","vibecheck":"✨ Vibe check","identity":"🃏 Oracle archetype","shadow":"🌑 Shadow self","element":"🌌 Cosmic element","corecode":"🔱 Core words","universe":"🌌 Universe message","ritual":"🕯️ Ritual","duality":"☯️ Duality","nightreport":"🌙 Night report","sigil":"🔱 Personal sigil","glitch":"⚡ Oracle glitch","checkin":"🌙 Daily check-in","streakcheck":"📊 Streak","coinboard":"🏆 Coin leaderboard","cgift":"💝 Gift coins","rob":"🦹 Rob coins","vent":"🫀 Anonymous vent","announce":"📢 Owner announcement","broadcast":"📣 Owner broadcast","midnightmap":"🗺️ Midnight Map"}; OWNER={"announce","broadcast","midnightmap"}
async def _set_commands(app):
    names=sorted([n for n in _command_names(app) if n and len(n)<=32])[:100]; public=[n for n in names if n not in OWNER]; make=lambda xs:[BotCommand(n,DESCRIPTIONS.get(n,"Midnight Oracle")) for n in xs]
    try:
        for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats(),BotCommandScopeAllChatAdministrators(),BotCommandScopeDefault()):
            await app.bot.delete_my_commands(scope=scope); await app.bot.set_my_commands(make(public),scope=scope)
        if OWNER_ID: await app.bot.set_my_commands(make(public+[n for n in names if n in OWNER]),scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception: log.exception("command menu setup failed")
async def _post_init(app):
    await _set_commands(app)
    try:
        from handlers.social_engine import init_storage
        init_storage(_storage_client)
    except Exception: log.exception("social storage init failed")
    try:
        from handlers.friend_engine import register
        register(app)
    except Exception: log.exception("FRIEND_ENGINE_REGISTRATION_FAILED")
    try:
        from handlers.presence_engine import register,silence_check
        register(app); app.job_queue.run_daily(silence_check,time=time(2,0,tzinfo=ORACLE_TZ),name="presence_silence_check")
    except Exception: log.exception("presence engine registration failed")
    log.info("AUTONOMOUS_CANONICAL_READY | legacy_social_scheduler=disabled | friend_engine=on")
    log.info("Post-init complete — Midnight Oracle is ready")
def _error(update,context): log.error("TELEGRAM_HANDLER_ERROR | update=%s | error=%r",getattr(update,"update_id","?"),context.error,exc_info=context.error)
def main():
    app=build_application(); app.post_init=_post_init; app.add_error_handler(_error); log.info("Midnight Oracle starting — instance %s",startup._INSTANCE_ID); asyncio.run(startup.run(app,storage_client=_storage_client))
if __name__=="__main__": main()