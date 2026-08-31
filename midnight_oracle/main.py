"""Canonical Midnight Oracle entry point: Phase 1–5 runtime + complete V2 ecosystem."""
from __future__ import annotations
import asyncio
from telegram import Update, WebAppInfo, MenuButtonWebApp
from telegram.ext import Application,CallbackQueryHandler,CommandHandler,MessageHandler,InlineQueryHandler,PollAnswerHandler,PollHandler,ContextTypes,filters
from .config import BOT_TOKEN,DATABASE_PATH,TIMEZONE
from .database import Database,now_ts
from .friend_engine import FriendEngine
from .memory_engine import MemoryEngine
from .mood_engine import MoodEngine
from .handlers.message_handler import MessageRouter
from .handlers.callback_handler import handle_callback
from .handlers.command_handler import start,oracle,truth,memory,mymemory,forget,quiet,wake,house,_house_url
from handlers.help_command import help_command,help_callback
from .handlers.inline_handler import handle_inline
from .handlers.world_handler import start_game,end_game,game_callback,handle_game_message,handle_poll_answer,handle_poll
from .handlers.prediction_handler import predict,predictions
from .handlers.webapp_handler import handle_webapp_data
from .handlers.surprise_handler import mysterybox,nightgift,muse,glitch
from .scheduler import OracleScheduler
from .utils.logger import configure_logging,get_logger
from storage import redis_client
log=get_logger('midnight.main')

async def _post_init(application:Application)->None:
    db=Database(DATABASE_PATH);await db.connect();mood=MoodEngine();mem=MemoryEngine(db);engine=FriendEngine(db,mood);router=MessageRouter(engine,mem,mood);application.bot_data.update(oracle_db=db,oracle_router=router,storage_client=redis_client)
    try:
        from handlers.runtime_registry import _set_commands
        await _set_commands(application);log.info('COMMAND_SURFACE_READY | source=canonical_runtime_registry')
    except Exception:log.exception('COMMAND_SURFACE_PUBLISH_FAILED')
    try:
        house_url=_house_url()
        if house_url:
            await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp('☾ Oracle House',web_app=WebAppInfo(url=house_url)))
            log.info('ORACLE_HOUSE_MENU_READY | webapp=configured')
        else:
            log.info('ORACLE_HOUSE_MENU_SKIPPED | webapp_url=not_configured')
    except Exception:log.exception('ORACLE_HOUSE_MENU_FAILED')
    try:
        from handlers import chat,social_engine
        await chat.load_from_storage()
        if not application.bot_data.get('_midnight_social_jobs_registered'):
            social_engine.init_storage(redis_client);social_engine.register_jobs(application);application.bot_data['_midnight_social_jobs_registered']=True
        log.info('SOCIAL_ENGINE_READY | pulse=registered | chat_settings=loaded')
    except Exception:log.exception('SOCIAL_ENGINE_START_FAILED')
    try:
        from core.oracle_pulse import install as install_oracle_pulse
        install_oracle_pulse(application)
        log.info('ORACLE_PULSE_READY | interval=90m | content=original_gossip_or_story | member_memory=excluded')
    except Exception:log.exception('ORACLE_PULSE_INSTALL_FAILED')
    scheduler=OracleScheduler(application,db,timezone=TIMEZONE);scheduler.start();application.bot_data['oracle_scheduler']=scheduler
    log.info('ORACLE_INTELLIGENCE_READY | friend_engine=on | memory=short+long | scheduler=on | social=on | pulse=on | world=on')

async def _post_shutdown(application:Application)->None:
    scheduler=application.bot_data.get('oracle_scheduler')
    if scheduler and scheduler.scheduler.running:scheduler.scheduler.shutdown(wait=False)
    db=application.bot_data.get('oracle_db')
    if db:await db.close()

async def _track_group_activity(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    chat=update.effective_chat;user=update.effective_user
    if not chat or chat.type not in {'group','supergroup'} or not user or user.is_bot:return
    db=context.application.bot_data.get('oracle_db')
    if not db:return
    try:
        await db.execute("INSERT INTO group_profile(group_id,group_name,timezone,created_at) VALUES(?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET group_name=excluded.group_name",(chat.id,chat.title or '',str(TIMEZONE),now_ts()))
        from handlers.social_engine import register_member,bump_msg_count
        await register_member(chat.id,user.id,user.first_name or 'Unknown',user.username or '');await bump_msg_count(chat.id,user.id)
    except Exception:log.exception('GROUP_ACTIVITY_TRACKING_FAILED | chat_id=%s',chat.id)

async def _route_message(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    chat=update.effective_chat
    if chat and chat.type in {'group','supergroup'}:
        await handle_game_message(update,context)
        db=context.application.bot_data.get('oracle_db')
        if db:
            row=await db.fetchone("SELECT game_type FROM game_sessions WHERE group_id=? AND is_active=1 LIMIT 1",(chat.id,))
            if row and row['game_type']=='word_scramble':return
        text=(update.effective_message.text or '').strip() if update.effective_message else ''
        low=text.casefold()
        username=str(getattr(context.bot,'username','') or '').casefold()
        replied=getattr(getattr(update.effective_message,'reply_to_message',None),'from_user',None) if update.effective_message else None
        bot_id=getattr(context.bot,'id',None)
        direct=bool(replied and bot_id and getattr(replied,'id',None)==bot_id) or bool(username and f'@{username}' in low) or low in {'oracle','midnight'} or any(low==p or low.startswith(p+' ') for p in ('hey oracle','hello oracle','hi oracle','oracle suno','oracle bhai','oracle bro','oracle listen','hey midnight','hello midnight','hi midnight','midnight suno','midnight bhai','midnight bro'))
        try:
            from core.storage import storage
            trigger=await storage.load(f'v2:autonomous:trigger:{chat.id}',None)
            if isinstance(trigger,str) and trigger and (low==trigger or low.startswith(trigger+' ')):direct=True
        except Exception:pass
        if not direct:
            try:
                from handlers.chat import chat_enabled
                if not chat_enabled.get(str(chat.id),False):return
            except Exception:return
    router=context.application.bot_data.get('oracle_router')
    if router:await router.handle(update,context)

def build_application()->Application:
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is required')
    app=Application.builder().token(BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()
    commands={'start':start,'help':help_command,'oracle':oracle,'truth':truth,'memory':memory,'mymemory':mymemory,'forget':forget,'quiet':quiet,'wake':wake,'house':house,'tod':start_game,'wyr':start_game,'nhie':start_game,'scramble':start_game,'unscramble':None,'predict':predict,'predictions':predictions,'endgame':end_game,'mysterybox':mysterybox,'nightgift':nightgift,'muse':muse,'glitch':glitch}
    for name,cb in commands.items():
        if name=='unscramble':
            from handlers.games import unscramble as cb
        group=-1 if name in {'help','start'} else 0
        app.add_handler(CommandHandler(name,cb),group=group)
    try:
        from handlers.legacy_surface import register_legacy_surface
        result=register_legacy_surface(app);log.info('LEGACY_SURFACE_WIRED | added=%d | skipped=%d',len(result.get('added',[])),len(result.get('skipped',[])))
    except Exception:log.exception('LEGACY_SURFACE_WIRING_FAILED')
    from core.v2_unique import register as register_v2_unique
    register_v2_unique(app)
    try:
        from handlers.relationship_engine import register as register_relationships
        register_relationships(app)
        log.info('RELATIONSHIP_SURFACE_WIRED')
    except Exception:log.exception('RELATIONSHIP_SURFACE_WIRING_FAILED')
    from core.v2_autonomous_commands import register as register_v2_autonomous_commands
    register_v2_autonomous_commands(app)
    from core.error_handling import install_error_handler
    install_error_handler(app)
    from core.sticker_reactions import install as install_sticker_reactions
    install_sticker_reactions(app)
    app.add_handler(MessageHandler(filters.ALL,_track_group_activity),group=-1000)
    app.add_handler(PollAnswerHandler(handle_poll_answer));app.add_handler(PollHandler(handle_poll));app.add_handler(CallbackQueryHandler(game_callback,pattern=r'^game:'));app.add_handler(CallbackQueryHandler(help_callback,pattern=r'^help:'));app.add_handler(CallbackQueryHandler(handle_callback));app.add_handler(InlineQueryHandler(handle_inline));app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA,handle_webapp_data));app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,_route_message));return app

def main()->None:
    """Run through the canonical startup manager so only one polling owner exists."""
    configure_logging()
    from startup import run as run_startup
    asyncio.run(run_startup(build_application(),redis_client))

if __name__=='__main__':main()
