"""Standalone Midnight Oracle entry point with Phase 2-4 surfaces."""
from __future__ import annotations
from telegram import Update
from telegram.ext import Application,CallbackQueryHandler,CommandHandler,MessageHandler,InlineQueryHandler,ContextTypes,filters
from .config import BOT_TOKEN,DATABASE_PATH
from .database import Database
from .friend_engine import FriendEngine
from .memory_engine import MemoryEngine
from .mood_engine import MoodEngine
from .handlers.message_handler import MessageRouter
from .handlers.callback_handler import handle_callback
from .handlers.command_handler import start,help_command,oracle,truth,memory,mymemory,forget,quiet,wake,house
from .handlers.inline_handler import handle_inline
from .handlers.world_handler import start_game,end_game,game_callback
from .handlers.prediction_handler import predict,predictions
from .handlers.webapp_handler import handle_webapp_data
from .scheduler import OracleScheduler
from .utils.logger import configure_logging,get_logger
log=get_logger('midnight.main')
async def _post_init(application:Application)->None:
    """Initialize persistence, Phase 1 engines, and autonomous scheduling."""
    db=Database(DATABASE_PATH); await db.connect(); mood=MoodEngine(); mem=MemoryEngine(db); engine=FriendEngine(db,mood); router=MessageRouter(engine,mem,mood); application.bot_data.update(oracle_db=db,oracle_router=router); scheduler=OracleScheduler(application,db); scheduler.start(); application.bot_data['oracle_scheduler']=scheduler; log.info('AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on | social=on | world=on')
async def _post_shutdown(application:Application)->None:
    """Close autonomous scheduling and SQLite resources."""
    scheduler=application.bot_data.get('oracle_scheduler');
    if scheduler and scheduler.scheduler.running:scheduler.scheduler.shutdown(wait=False)
    db=application.bot_data.get('oracle_db');
    if db:await db.close()
async def _route_message(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Route non-command text through the existing Phase 1 router."""
    router=context.application.bot_data.get('oracle_router');
    if router:await router.handle(update,context)
def build_application()->Application:
    """Construct the single-process Telegram application."""
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is required')
    app=Application.builder().token(BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build(); commands={'start':start,'help':help_command,'oracle':oracle,'truth':truth,'memory':memory,'mymemory':mymemory,'forget':forget,'quiet':quiet,'wake':wake,'house':house,'tod':start_game,'wyr':start_game,'nhie':start_game,'scramble':start_game,'predict':predict,'predictions':predictions,'endgame':end_game}
    for name,cb in commands.items():app.add_handler(CommandHandler(name,cb))
    app.add_handler(CallbackQueryHandler(game_callback,pattern=r'^game:')); app.add_handler(CallbackQueryHandler(handle_callback)); app.add_handler(InlineQueryHandler(handle_inline)); app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA,handle_webapp_data)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,_route_message)); return app
def main()->None:
    """Start the polling application."""; configure_logging(); build_application().run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()
