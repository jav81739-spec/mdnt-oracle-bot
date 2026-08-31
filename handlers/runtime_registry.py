"""Canonical Telegram handler/lifecycle registry for Midnight Oracle."""
from __future__ import annotations
import logging
from datetime import datetime
from telegram import BotCommand,BotCommandScopeAllGroupChats,BotCommandScopeAllPrivateChats
from telegram.ext import Application,CommandHandler,MessageHandler,filters
import legacy_bot
from handlers import chat,games,moderation,utility,aesthetic,friendship,fun,matchmaking,stats,events,economy,timecapsule,marriage
try:
    from handlers import deathgames_v2 as deathgames
except ImportError:
    from handlers import deathgames
log=logging.getLogger("midnight.registry")

def build_application(token,storage_client):
    app=Application.builder().token(token).build()
    async def chat_registry(update,context):
        chat_obj=getattr(update,"effective_chat",None)
        if chat_obj and chat_obj.type in ("group","supergroup","channel"):
            try:
                from startup import register_chat
                await register_chat(chat_obj.id,chat_obj.type,chat_obj.title or "")
            except Exception:log.exception("CHAT_REGISTRY_FAILED | chat_id=%s",getattr(chat_obj,"id",None))
    app.add_handler(MessageHandler(filters.ALL,chat_registry),group=-999)
    try:
        from handlers.engagement_engine import init_storage as init_engagement_storage,register as register_engagement
        init_engagement_storage(storage_client);register_engagement(app)
    except ModuleNotFoundError:log.info("Optional engagement_engine not present")
    except Exception:log.exception("Optional engagement registration failed")
    if hasattr(legacy_bot,"register_handlers"):legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot,"_register_handlers"):legacy_bot._register_handlers(app)
    else:_shim_register(app)
    for name in ("broadcast","announce"):
        cb=getattr(legacy_bot,f"{name}_command",None)
        if cb:app.add_handler(CommandHandler(name,cb))
    try:
        from handlers.midnightmap import midnightmap_command
        app.add_handler(CommandHandler("midnightmap",midnightmap_command))
    except Exception:log.exception("MIDNIGHTMAP_REGISTRATION_FAILED")
    return app

def _shim_register(app):
    command_map={"oracle":"oracle_new_command","aura":"aura_command","identity":"identity_command","vibecheck":"vibecheck_command","shadow":"shadow_command","element":"element_command","corecode":"corecode_command","universe":"universe_command","ritual":"ritual_command","duality":"duality_command","glitch":"glitch_command","nightreport":"nightreport_command","sigil":"sigil_command","checkin":"checkin_command","streakcheck":"streakcheck_command","vent":"vent_command","cgift":"cgift_command","rob":"eng_rob_command","coinboard":"coinboard_command"}
    for cmd,fn in command_map.items():
        cb=getattr(legacy_bot,fn,None)
        if cb:app.add_handler(CommandHandler(cmd,cb))
    for module in (chat,games,moderation,utility,aesthetic,friendship,fun,matchmaking,stats,events,economy,timecapsule,marriage,deathgames):
        register=getattr(module,"register",None)
        if register:
            try:register(app)
            except Exception:log.exception("LEGACY_MODULE_REGISTER_FAILED | module=%s",getattr(module,"__name__",module))
    cb=getattr(legacy_bot,"handle_ai_message",None)
    if cb:app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,cb),group=10)
    sticker=getattr(legacy_bot,"handle_sticker",None) or getattr(legacy_bot,"smart_sticker_reply",None)
    if sticker:app.add_handler(MessageHandler(filters.Sticker.ALL,sticker))

def _live_public_commands(app):
    excluded={"broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload","shutdown","restart","admin","moderation"}
    names={"start","help"}
    for handlers in getattr(app,"handlers",{}).values():
        for handler in handlers:
            if isinstance(handler,CommandHandler):
                for command in getattr(handler,"commands",()):
                    name=str(command).lower().lstrip("/")
                    if name and name not in excluded and len(name)<=32:names.add(name)
    return sorted(names)

async def _set_commands(app):
    names=_live_public_commands(app)
    priority=["start","help","oracle","truth","dare","wyr","nhie","rps","riddle","scramble","guess","quiz","hug","kiss","pat","cuddle","wave","wink","roast","cheer","comfort","bond","friendship","ship","bestie","duo","matchmaker","memory","mymemory","forget","house","quiet","wake","cricket","cricketduel","leaderboard","dice","darts","basketball","bowling","football","mysterybox","muse","nightgift","glitch"]
    rank={n:i for i,n in enumerate(priority)};ordered=sorted(names,key=lambda n:(rank.get(n,10000),n));visible=ordered[:100]
    descriptions={"start":"☾ Meet Midnight Oracle","help":"✦ Member command archive","oracle":"🔮 Get a reading","truth":"💭 Truth question","dare":"🔥 Take a dare","wyr":"⚖️ Would you rather","nhie":"🙈 Never have I ever","rps":"✋ Rock paper scissors","riddle":"🧩 Solve a riddle","scramble":"🔤 Unscramble a word","guess":"🎯 Make a guess","quiz":"🧠 Take a quiz","hug":"🫂 Send a hug","kiss":"💋 Send a kiss","pat":"🫳 Give a pat","cuddle":"🫶 Cuddle","wave":"👋 Wave","wink":"😉 Wink","roast":"🔥 Roast","cheer":"✨ Cheer","comfort":"🫂 Comfort someone","bond":"🪢 Read a bond","friendship":"💞 Friendship","ship":"💫 Ship two souls","bestie":"🌙 Find a bestie","duo":"♾️ Find a duo","matchmaker":"💘 Matchmaker","memory":"🧠 Group memory","mymemory":"🫀 What Oracle remembers","forget":"🕯️ Forget a memory","house":"🏠 Oracle House","quiet":"🌑 Quiet Oracle","wake":"☀️ Wake Oracle","cricket":"🏏 Solo cricket","cricketduel":"🏏 Cricket duel","leaderboard":"🏆 Leaderboard","dice":"🎲 Roll the dice","darts":"🎯 Play darts","basketball":"🏀 Basketball","bowling":"🎳 Bowling","football":"⚽ Football","mysterybox":"🎁 Open a rare mystery","muse":"✦ Find a spark","nightgift":"🌙 Receive a tiny gift","glitch":"🪞 Inspect a harmless glitch"}
    commands=[BotCommand(n,descriptions.get(n,"☾ Midnight Oracle")) for n in visible]
    for scope in (BotCommandScopeAllPrivateChats(),BotCommandScopeAllGroupChats(),None):
        try:
            if scope is None:await app.bot.set_my_commands(commands)
            else:await app.bot.set_my_commands(commands,scope=scope)
        except Exception:log.exception("COMMAND_MENU_PUBLISH_FAILED")
    if len(names)>100:log.info("COMMAND_MENU_CAPPED | total_live=%d | native_menu=100 | full_archive=help",len(names))
    return names

def configure_lifecycle(app,storage_client,oracle_tz):
    async def post_init():
        live_commands=await _set_commands(app)
        from handlers.social_engine import register_jobs,init_storage
        from handlers.presence_engine import register as register_presence,silence_check
        from handlers.help_command import register as help_register
        from handlers.homecoming import homecoming_job
        from handlers import social_engine,surprise_engine
        from handlers.oracle_governor import install as install_oracle_governor
        init_storage(storage_client);install_oracle_governor(social_engine);register_jobs(app);register_presence(app);surprise_engine.register(app);help_register(app)
        jq=app.job_queue
        if jq:
            jq.run_repeating(homecoming_job,interval=21600,first=30,name="hidden_homecoming")
            jq.run_daily(silence_check,time=datetime.now(oracle_tz).replace(hour=2,minute=0,second=0,microsecond=0).timetz(),name="silence_check")
            log.info("AUTOMATION_SCHEDULER_READY | jobs=%d",len(jq.jobs()))
        else:log.error("AUTOMATION_SCHEDULER_DISABLED | JobQueue unavailable")
        if hasattr(legacy_bot,"_post_init"):
            try:await legacy_bot._post_init(app)
            except Exception:log.exception("legacy_bot._post_init failed")
        log.info("Post-init complete | live_member_commands=%d",len(live_commands))
    original_initialize=app.initialize;hooks_ran=False
    async def initialize_with_hooks():
        nonlocal hooks_ran
        await original_initialize()
        if not hooks_ran:
            hooks_ran=True;await post_init()
    app.initialize=initialize_with_hooks
    return app
