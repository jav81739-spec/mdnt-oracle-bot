"""
bot.py — Midnight Oracle | One canonical entrypoint.

This is the ONLY file Render should run: python bot.py
Delete bot2.py, bot3.py, bot_1.py — they are dead duplicates.

Architecture:
  bot.py
    └── startup.py      (lease, health, shutdown, chat registry)
    └── legacy_bot.py   (all handlers, Gemini, GIPHY, stickers, Baka/Nova)
    └── storage.py      (Redis compat facade → core/storage)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# ── PATH ──────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Logging (must come first) ──────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("midnight.bot")

# ── Env ────────────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    log.critical("BOT_TOKEN is not set. Add it to .env or Render environment.")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    log.warning("GEMINI_API_KEY not set — AI replies will use fallback responses.")

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
if GROUP_CHAT_ID == 0:
    log.warning(
        "GROUP_CHAT_ID not set — scheduled/broadcast group messages will be skipped. "
        "Use /id in your group to get the ID."
    )

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
if OWNER_ID == 0:
    log.warning("OWNER_ID not set — owner-only commands will be unavailable.")

ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata"))

# ── Storage ────────────────────────────────────────────────────────────────────
try:
    from storage import redis_client as _storage_client
    log.info("Storage: using storage.RedisCompat → core.storage")
except Exception as _e:
    log.warning("storage.py import failed (%s) — storage features disabled", _e)
    _storage_client = None

# ── Startup manager ────────────────────────────────────────────────────────────
import startup
startup.init(_storage_client)

# ── PTB Application ────────────────────────────────────────────────────────────
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters
from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
)

# ── Import legacy_bot for all handlers ────────────────────────────────────────
#
# legacy_bot.py contains ALL the actual bot logic: handlers, Gemini, GIPHY,
# stickers, Baka/Nova, economy, games, moderation, etc.
# We import it and wire its handlers into the Application below.
# We do NOT call legacy_bot.main() — startup.py owns the lifecycle.
#
import legacy_bot

# Fix: override Gemini model default in legacy_bot if it has the wrong one
if hasattr(legacy_bot, "GEMINI_MODEL"):
    current = legacy_bot.GEMINI_MODEL
    bad_models = {"gemini-3.7-flash", "gemini-3.5-flash-lite"}
    if current in bad_models:
        good = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        log.warning("Fixing wrong GEMINI_MODEL '%s' → '%s'", current, good)
        legacy_bot.GEMINI_MODEL = good

# Fix: inject GROUP_CHAT_ID guard into legacy_bot
if hasattr(legacy_bot, "GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID == 0:
    legacy_bot.GROUP_CHAT_ID = GROUP_CHAT_ID


# ── Chat registry middleware ───────────────────────────────────────────────────
# Auto-discover every group/channel the bot is active in.

async def _chat_registry_middleware(update, context):
    """Called on every update — registers the chat so broadcast works."""
    chat = getattr(update, "effective_chat", None)
    if chat and chat.type in ("group", "supergroup", "channel"):
        await startup.register_chat(
            chat_id=chat.id,
            chat_type=chat.type,
            title=chat.title or "",
        )


# ── Build Application ─────────────────────────────────────────────────────────

def build_application() -> Application:
    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Chat registry middleware runs on all updates
    app.add_handler(
        MessageHandler(filters.ALL, _chat_registry_middleware),
        group=-999,  # very high priority, runs before all handlers
    )
    from handlers.social_engine import track_member
    app.add_handler(MessageHandler(filters.ALL, track_member), group=-998)

    # Register all handlers from legacy_bot
    # legacy_bot.register_handlers(app) if it has that function,
    # otherwise call legacy_bot's own handler registration.
    if hasattr(legacy_bot, "register_handlers"):
        legacy_bot.register_handlers(app)
        log.info("Handlers registered via legacy_bot.register_handlers()")
    elif hasattr(legacy_bot, "_register_handlers"):
        legacy_bot._register_handlers(app)
        log.info("Handlers registered via legacy_bot._register_handlers()")
    else:
        # legacy_bot uses its own main() to register — extract what we need
        log.warning(
            "legacy_bot has no register_handlers() — "
            "attempting to pull handlers via legacy_bot.main() shim"
        )
        _shim_register(app)

    return app


def _shim_register(app: Application):
    """
    Fallback: legacy_bot.main() creates its own Application internally.
    We extract the handlers it would register and add them to our app instead.
    This avoids legacy_bot starting its own conflicting polling loop.
    """
    # The handlers legacy_bot registers are known from reading legacy_bot.py.
    # We wire them manually here so startup.py owns the lifecycle.

    from handlers import (
        chat, games, moderation, utility, aesthetic,
        friendship, fun, matchmaking, stats,
        events, economy, timecapsule, marriage,
    )
    try:
        from handlers import deathgames_v2 as deathgames
    except ImportError:
        from handlers import deathgames

    from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters

    # ── Oracle / AI ────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("oracle",      legacy_bot.oracle_new_command))
    app.add_handler(CommandHandler("aura",        legacy_bot.aura_command))
    app.add_handler(CommandHandler("identity",    legacy_bot.identity_command))
    app.add_handler(CommandHandler("vibecheck",   legacy_bot.vibecheck_command))
    app.add_handler(CommandHandler("shadow",      legacy_bot.shadow_command))
    app.add_handler(CommandHandler("element",     legacy_bot.element_command))
    app.add_handler(CommandHandler("corecode",    legacy_bot.corecode_command))
    app.add_handler(CommandHandler("universe",    legacy_bot.universe_command))
    app.add_handler(CommandHandler("ritual",      legacy_bot.ritual_command))
    app.add_handler(CommandHandler("duality",     legacy_bot.duality_command))
    app.add_handler(CommandHandler("glitch",      legacy_bot.glitch_command))
    app.add_handler(CommandHandler("nightreport", legacy_bot.nightreport_command))
    app.add_handler(CommandHandler("sigil",       legacy_bot.sigil_command))

    # ── Engagement ─────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("checkin",     legacy_bot.checkin_command))
    app.add_handler(CommandHandler("streakcheck", legacy_bot.streakcheck_command))
    app.add_handler(CommandHandler("vent",        legacy_bot.vent_command))
    app.add_handler(CommandHandler("cgift",       legacy_bot.cgift_command))
    app.add_handler(CommandHandler("rob",         legacy_bot.eng_rob_command))
    app.add_handler(CommandHandler("coinboard",   legacy_bot.coinboard_command))

    # ── Handlers from handler modules ──────────────────────────────────────
    if hasattr(chat, "register"):         chat.register(app)
    if hasattr(games, "register"):        games.register(app)
    if hasattr(moderation, "register"):   moderation.register(app)
    if hasattr(utility, "register"):      utility.register(app)
    if hasattr(aesthetic, "register"):    aesthetic.register(app)
    if hasattr(friendship, "register"):   friendship.register(app)
    if hasattr(fun, "register"):          fun.register(app)
    if hasattr(matchmaking, "register"):  matchmaking.register(app)
    if hasattr(stats, "register"):        stats.register(app)
    if hasattr(events, "register"):       events.register(app)
    if hasattr(economy, "register"):      economy.register(app)
    if hasattr(timecapsule, "register"):  timecapsule.register(app)
    if hasattr(marriage, "register"):     marriage.register(app)
    if hasattr(deathgames, "register"):   deathgames.register(app)

    # ── AI message handler (catch-all, lowest priority) ────────────────────
    if hasattr(legacy_bot, "handle_ai_message"):
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                legacy_bot.handle_ai_message,
            ),
            group=10,
        )

    # ── Channel post handler ────────────────────────────────────────────────
    if hasattr(legacy_bot, "handle_channel_post"):
        app.add_handler(
            MessageHandler(filters.IS_AUTOMATIC_FORWARD, legacy_bot.handle_channel_post)
        )

    # ── Sticker handler ────────────────────────────────────────────────────
    if hasattr(legacy_bot, "handle_sticker"):
        app.add_handler(
            MessageHandler(filters.Sticker.ALL, legacy_bot.handle_sticker)
        )

    log.info("Handlers registered via shim (legacy_bot internals)")


# ── Set Telegram command menu ─────────────────────────────────────────────────

async def _set_commands(app: Application):
    """Register the current Midnight Oracle command menu in private chats and groups."""
    commands = [
        BotCommand("start",       "🌙 Enter the Midnight Realm"),
        BotCommand("help",        "📖 See what Midnight Oracle can do"),
        BotCommand("oracle",      "🔮 Your daily Oracle prophecy"),
        BotCommand("aura",        "🟣 Scan your aura"),
        BotCommand("vibecheck",   "✨ Vibe check"),
        BotCommand("identity",    "🃏 Your Oracle archetype"),
        BotCommand("shadow",      "🌑 Meet your shadow self"),
        BotCommand("element",     "🌌 Your cosmic element"),
        BotCommand("corecode",    "🔱 Your core words"),
        BotCommand("universe",    "🌌 Message from the universe"),
        BotCommand("ritual",      "🕯️ Today's ritual"),
        BotCommand("duality",     "☯️ Your duality"),
        BotCommand("nightreport", "🌙 Tonight's night report"),
        BotCommand("sigil",       "🔱 Your personal sigil"),
        BotCommand("glitch",      "⚡ Oracle glitch"),
        BotCommand("checkin",     "🌙 Daily check-in & streak"),
        BotCommand("streakcheck", "📊 Check your streak"),
        BotCommand("coinboard",   "🏆 Coin leaderboard"),
        BotCommand("cgift",       "💝 Gift coins to someone"),
        BotCommand("rob",         "🦹 Rob someone's coins"),
        BotCommand("vent",        "🫀 Anonymous vent"),
    ]
    try:
        # Remove older scoped menus before installing the current one.
        # This clears the stale private/group/admin menus seen after the upgrade.
        await app.bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        await app.bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
        await app.bot.delete_my_commands(scope=BotCommandScopeAllChatAdministrators())
        await app.bot.delete_my_commands(scope=BotCommandScopeDefault())

        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllChatAdministrators())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        log.info("Telegram command menus set (%d commands) for private, group, admin and default scopes", len(commands))
    except Exception as exc:
        log.warning("Could not set command menu: %s", exc)


# ── Post-init hook ────────────────────────────────────────────────────────────

async def _post_init(app: Application):
    """Called by PTB after initialization — safe place for async setup."""
    await _set_commands(app)

    from handlers.social_engine import register_jobs, init_storage, track_member
    from handlers.presence_engine import register, silence_check
    from handlers.help_command import register as help_register

    # Give social engine access to storage
    init_storage(_storage_client)

    # Register jobs (scheduled auto-posts)
    register_jobs(app)

    # Register presence engine message handler
    register(app)

    # Register help/start
    help_register(app)

    # Schedule daily silence check (2 AM)
    app.job_queue.run_daily(
        silence_check,
        time=datetime.now(ORACLE_TZ).replace(hour=2, minute=0, second=0).timetz(),
    )

    # Run legacy_bot's own post_init if it has one
    if hasattr(legacy_bot, "_post_init"):
        try:
            await legacy_bot._post_init(app)
        except Exception as exc:
            log.warning("legacy_bot._post_init failed: %s", exc)

    log.info("Post-init complete — Midnight Oracle is ready")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = build_application()

    # Attach post_init hook
    app.post_init = _post_init

    log.info("Midnight Oracle starting — instance %s", startup._INSTANCE_ID)
    asyncio.run(startup.run(app, storage_client=_storage_client))


if __name__ == "__main__":
    main()
