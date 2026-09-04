"""Canonical Midnight Oracle runtime with the complete preserved surface."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, InlineQueryHandler, PollAnswerHandler, PollHandler, ContextTypes, filters

from .config import BOT_TOKEN, DATABASE_PATH
from .database import Database
from .friend_engine import FriendEngine
from .memory_engine import MemoryEngine
from .mood_engine import MoodEngine
from .handlers.message_handler import MessageRouter
from .handlers.callback_handler import handle_callback
from .handlers.command_handler import start, help_command, oracle, truth, memory, mymemory, forget, quiet, wake, house
from .handlers.inline_handler import handle_inline
from .handlers.world_handler import start_game, end_game, game_callback, handle_game_message, handle_poll_answer, handle_poll
from .handlers.prediction_handler import predict, predictions
from .handlers.webapp_handler import handle_webapp_data
from .handlers.surprise_handler import mysterybox, nightgift, muse, glitch
from .handlers.voice_handler import voice
from .scheduler import OracleScheduler
from .utils.logger import configure_logging, get_logger

log = get_logger("midnight.main")


def _add_handler_once(app: Application, handler, *, group: int = 0) -> None:
    """Add a handler only when an equivalent command/callback surface is absent."""
    commands = {str(c).lower().lstrip("/") for hs in getattr(app, "handlers", {}).values() for h in hs for c in (getattr(h, "commands", None) or ())}
    wanted = {str(c).lower().lstrip("/") for c in (getattr(handler, "commands", None) or ())}
    if wanted and wanted & commands:
        return
    callback = getattr(handler, "callback", None)
    if callback is not None and any(getattr(h, "callback", None) is callback for hs in getattr(app, "handlers", {}).values() for h in hs):
        return
    app.add_handler(handler, group=group)


def _register_preserved_surfaces(application: Application) -> None:
    """Register the complete preserved feature surface before runtime startup."""
    try:
        from handlers.legacy_surface import register_legacy_surface
        result = register_legacy_surface(application)
        log.info("LEGACY_SURFACE_WIRED | added=%d | skipped=%d", len(result.get("added", [])), len(result.get("skipped", [])))
    except Exception:
        log.exception("LEGACY_SURFACE_WIRING_FAILED")
        raise
    try:
        from handlers.organic_relationships import ship
        _add_handler_once(application, CommandHandler("ship", ship), group=-40)
        log.info("ORGANIC_RELATIONSHIP_SURFACE_READY | ship=on")
    except Exception:
        log.exception("ORGANIC_RELATIONSHIP_SURFACE_WIRING_FAILED")
        raise
    for label, importer in (
        ("FRIEND_SURFACE", "handlers.friend_engine"),
        ("V2_UNIQUE_SURFACE", "core.v2_unique"),
        ("ORACLE_INSTINCT_SURFACE", "core.oracle_instinct_commands"),
        ("OWNER_CONSOLE_SURFACE", "handlers.owner_console_v2"),
        ("MEMORIAL_SURFACE", "handlers.memorial"),
    ):
        try:
            module = __import__(importer, fromlist=["register"])
            register = getattr(module, "register")
            register(application)
        except Exception:
            log.exception("%s_WIRING_FAILED", label)
            raise
    log.info("PRESERVED_SURFACE_READY | legacy=on | friend=on | v2_unique=on | instinct=on | owner=on | memorial=on")


async def _post_init(application: Application) -> None:
    """Initialize persistence, canonical engines, scheduler and runtime bridges."""
    from core.storage import storage
    db = Database(DATABASE_PATH)
    await db.connect()
    mood = MoodEngine()
    mem = MemoryEngine(db)
    engine = FriendEngine(db, mood)
    router = MessageRouter(engine, mem, mood)
    application.bot_data.update(oracle_db=db, oracle_router=router, storage_client=storage)
    scheduler = OracleScheduler(application, db)
    scheduler.start()
    application.bot_data["oracle_scheduler"] = scheduler
    log.info("AUTONOMOUS_CANONICAL_READY | friend_engine=on | memory=on | scheduler=on | social=on | world=on | surprise=on | voice=on | legacy_surface=on | v2_unique=on | storage=on")


async def _post_shutdown(application: Application) -> None:
    """Close scheduler and SQLite resources."""
    scheduler = application.bot_data.get("oracle_scheduler")
    if scheduler and scheduler.scheduler.running:
        scheduler.scheduler.shutdown(wait=False)
    db = application.bot_data.get("oracle_db")
    if db:
        await db.close()


def _route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route active games first, then canonical human conversation."""
    raise RuntimeError("_route_message must be async")


async def _route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route active games first, then canonical human conversation."""
    if update.effective_chat and update.effective_chat.type in {"group", "supergroup"}:
        await handle_game_message(update, context)
        db = context.application.bot_data.get("oracle_db")
        if db:
            row = await db.fetchone("SELECT game_type FROM game_sessions WHERE group_id=? AND is_active=1 LIMIT 1", (update.effective_chat.id,))
            if row and row["game_type"] == "word_scramble":
                return
    router = context.application.bot_data.get("oracle_router")
    if router:
        await router.handle(update, context)


def _install_world_lifecycle(app: Application) -> None:
    """Install poll/callback/game lifecycle handlers exactly once."""
    _add_handler_once(app, PollAnswerHandler(handle_poll_answer), group=-30)
    _add_handler_once(app, PollHandler(handle_poll), group=-30)
    _add_handler_once(app, CallbackQueryHandler(game_callback, pattern=r"^game:"), group=-30)
    _add_handler_once(app, CallbackQueryHandler(handle_callback, pattern=r"^(?:reveal_|secret:).+"), group=-29)
    _add_handler_once(app, InlineQueryHandler(handle_inline), group=-30)
    _add_handler_once(app, MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data), group=-30)
    _add_handler_once(app, MessageHandler(filters.TEXT & ~filters.COMMAND,_route_message), group=-29)


def build_application() -> Application:
    """Construct the single-process Telegram application with preserved surfaces."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")
    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()
    commands = {
        "start": start, "help": help_command, "oracle": oracle, "truth": truth,
        "memory": memory, "mymemory": mymemory, "forget": forget, "quiet": quiet,
        "wake": wake, "house": house, "voice": voice,
        "tod": start_game, "wyr": start_game, "nhie": start_game, "scramble": start_game,
        "predict": predict, "predictions": predictions, "endgame": end_game,
        "mysterybox": mysterybox, "nightgift": nightgift, "muse": muse, "glitch": glitch,
    }
    for name, callback in commands.items():
        _add_handler_once(app, CommandHandler(name, callback), group=-30)
    _install_world_lifecycle(app)
    _register_preserved_surfaces(app)
    return app


def main() -> None:
    """Start polling through the single canonical startup manager."""
    configure_logging()
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
