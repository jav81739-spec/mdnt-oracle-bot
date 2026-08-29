"""Standalone Phase 1 entry point for Midnight Oracle."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
from .config import BOT_TOKEN, DATABASE_PATH
from .database import Database
from .friend_engine import FriendEngine
from .memory_engine import MemoryEngine
from .mood_engine import MoodEngine
from .handlers.message_handler import MessageRouter
from .handlers.callback_handler import handle_callback
from .handlers.command_handler import start, help_command, oracle, truth, memory, mymemory, forget, quiet, wake
from .scheduler import OracleScheduler
from .utils.logger import configure_logging, get_logger

log = get_logger("midnight.main")


async def _post_init(application: Application) -> None:
    """Initialize persistence, engines, and autonomous scheduling."""
    db = Database(DATABASE_PATH)
    await db.connect()
    mood = MoodEngine()
    mem = MemoryEngine(db)
    engine = FriendEngine(db, mood)
    router = MessageRouter(engine, mem, mood)
    application.bot_data["oracle_db"] = db
    application.bot_data["oracle_router"] = router
    scheduler = OracleScheduler(application, db)
    scheduler.start()
    application.bot_data["oracle_scheduler"] = scheduler
    log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on")


async def _post_shutdown(application: Application) -> None:
    """Close persistent resources cleanly during application shutdown."""
    scheduler = application.bot_data.get("oracle_scheduler")
    if scheduler and scheduler.scheduler.running:
        scheduler.scheduler.shutdown(wait=False)
    db = application.bot_data.get("oracle_db")
    if db:
        await db.close()


async def _route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route non-command Telegram messages through the Friend Engine."""
    router = context.application.bot_data.get("oracle_router")
    if router:
        await router.handle(update, context)


def build_application() -> Application:
    """Construct the standalone Telegram application."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")
    application = Application.builder().token(BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()
    for name, callback in (("start", start), ("help", help_command), ("oracle", oracle), ("truth", truth), ("memory", memory), ("mymemory", mymemory), ("forget", forget), ("quiet", quiet), ("wake", wake)):
        application.add_handler(CommandHandler(name, callback))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _route_message))
    return application


def main() -> None:
    """Start the single-process polling application."""
    configure_logging()
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
