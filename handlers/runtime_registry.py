"""Canonical Telegram handler/lifecycle registry for Midnight Oracle.

Kept outside bot.py so the production entrypoint remains a tiny lifecycle adapter.
"""
from __future__ import annotations

import logging
from datetime import datetime

from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import legacy_bot
from handlers import (
    chat, games, moderation, utility, aesthetic, friendship, fun,
    matchmaking, stats, events, economy, timecapsule, marriage,
)

try:
    from handlers import deathgames_v2 as deathgames
except ImportError:
    from handlers import deathgames

log = logging.getLogger("midnight.registry")


def build_application(token, storage_client):
    """Build the single Telegram application while preserving legacy handlers."""
    app = Application.builder().token(token).build()

    async def chat_registry(update, context):
        """Record chats as soon as Telegram delivers an update from them."""
        chat_obj = getattr(update, "effective_chat", None)
        if chat_obj and chat_obj.type in ("group", "supergroup", "channel"):
            try:
                from startup import register_chat
                await register_chat(chat_obj.id, chat_obj.type, chat_obj.title or "")
            except Exception:
                log.exception("CHAT_REGISTRY_FAILED | chat_id=%s", getattr(chat_obj, "id", None))

    app.add_handler(MessageHandler(filters.ALL, chat_registry), group=-999)

    try:
        from handlers.engagement_engine import (
            init_storage as init_engagement_storage,
            register as register_engagement,
        )
        init_engagement_storage(storage_client)
        register_engagement(app)
    except ModuleNotFoundError:
        log.info("Optional engagement_engine not present; continuing with canonical social engine")
    except Exception:
        log.exception("Optional engagement registration failed; continuing")

    if hasattr(legacy_bot, "register_handlers"):
        legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot, "_register_handlers"):
        legacy_bot._register_handlers(app)
    else:
        _shim_register(app)

    if hasattr(legacy_bot, "broadcast_command"):
        app.add_handler(CommandHandler("broadcast", legacy_bot.broadcast_command))
    if hasattr(legacy_bot, "announce_command"):
        app.add_handler(CommandHandler("announce", legacy_bot.announce_command))

    try:
        from handlers.midnightmap import midnightmap_command
        app.add_handler(CommandHandler("midnightmap", midnightmap_command))
    except Exception:
        log.exception("MIDNIGHTMAP_REGISTRATION_FAILED")

    return app


def _shim_register(app):
    """Register the legacy command/module surface when legacy_bot has no registry."""
    command_map = {
        "oracle": "oracle_new_command", "aura": "aura_command", "identity": "identity_command",
        "vibecheck": "vibecheck_command", "shadow": "shadow_command", "element": "element_command",
        "corecode": "corecode_command", "universe": "universe_command", "ritual": "ritual_command",
        "duality": "duality_command", "glitch": "glitch_command", "nightreport": "nightreport_command",
        "sigil": "sigil_command", "checkin": "checkin_command", "streakcheck": "streakcheck_command",
        "vent": "vent_command", "cgift": "cgift_command", "rob": "eng_rob_command", "coinboard": "coinboard_command",
    }
    for cmd, fn in command_map.items():
        handler = getattr(legacy_bot, fn, None)
        if handler:
            app.add_handler(CommandHandler(cmd, handler))

    for module in (chat, games, moderation, utility, aesthetic, friendship, fun,
                   matchmaking, stats, events, economy, timecapsule, marriage, deathgames):
        if hasattr(module, "register"):
            try:
                module.register(app)
            except Exception:
                log.exception("LEGACY_MODULE_REGISTER_FAILED | module=%s", getattr(module, "__name__", module))

    if hasattr(legacy_bot, "handle_ai_message"):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, legacy_bot.handle_ai_message), group=10)
    sticker_handler = getattr(legacy_bot, "handle_sticker", None) or getattr(legacy_bot, "smart_sticker_reply", None)
    if sticker_handler:
        app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))


def _live_public_commands(app) -> list[str]:
    """Return executable member commands, excluding owner/admin-only controls."""
    excluded = {
        "broadcast", "announce", "midnightmap", "ownerstatus", "ownerstats",
        "setcommands", "reload", "shutdown", "restart", "admin", "moderation",
    }
    names: set[str] = {"start", "help"}
    for handlers in getattr(app, "handlers", {}).values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                for command in getattr(handler, "commands", ()):
                    command = str(command).lower().lstrip("/")
                    if command and command not in excluded and len(command) <= 32:
                        names.add(command)
    return sorted(names)


async def _set_commands(app):
    """Publish every currently registered member command to all public scopes.

    Telegram's native menu accepts at most 100 commands. Nothing is deleted from
    the executable registry when there are more: /help remains the complete
    member directory, while the native menu prioritizes the most useful member
    commands in a stable order.
    """
    names = _live_public_commands(app)
    priority = [
        "start", "help", "oracle", "truth", "dare", "wyr", "nhie", "rps", "riddle",
        "scramble", "guess", "quiz", "hug", "kiss", "pat", "cuddle", "wave", "wink",
        "roast", "cheer", "comfort", "bond", "friendship", "ship", "bestie", "duo",
        "matchmaker", "memory", "mymemory", "forget", "house", "quiet", "wake",
        "cricket", "cricketduel", "leaderboard", "dice", "darts", "basketball", "bowling", "football",
    ]
    rank = {name: index for index, name in enumerate(priority)}
    ordered = sorted(names, key=lambda name: (rank.get(name, 10_000), name))
    visible = ordered if len(ordered) < 100 else ordered[:100]

    descriptions = {
        "start": "☾ Meet Midnight Oracle", "help": "✦ Member command archive", "oracle": "🔮 Get a reading",
        "truth": "💭 Truth question", "dare": "🔥 Take a dare", "wyr": "⚖️ Would you rather",
        "nhie": "🙈 Never have I ever", "rps": "✋ Rock paper scissors", "riddle": "🧩 Solve a riddle",
        "scramble": "🔤 Unscramble a word", "guess": "🎯 Make a guess", "quiz": "🧠 Take a quiz",
        "hug": "🫂 Send a hug", "kiss": "💋 Send a kiss", "pat": "🫳 Give a pat", "cuddle": "🫶 Cuddle",
        "wave": "👋 Wave", "wink": "😉 Wink", "roast": "🔥 Roast", "cheer": "✨ Cheer",
        "comfort": "🫂 Comfort someone", "bond": "🪢 Read a bond", "friendship": "💞 Friendship",
        "ship": "💫 Ship two souls", "bestie": "🌙 Find a bestie", "duo": "♾️ Find a duo",
        "matchmaker": "💘 Matchmaker", "memory": "🧠 Group memory", "mymemory": "🫀 What Oracle remembers",
        "forget": "🕯️ Forget a memory", "house": "🏠 Oracle House", "quiet": "🌑 Quiet Oracle", "wake": "☀️ Wake Oracle",
        "cricket": "🏏 Solo cricket", "cricketduel": "🏏 Cricket duel", "leaderboard": "🏆 Leaderboard",
        "dice": "🎲 Roll the dice", "darts": "🎯 Play darts", "basketball": "🏀 Basketball",
        "bowling": "🎳 Bowling", "football": "⚽ Football",
    }
    commands = [BotCommand(name, descriptions.get(name, "☾ Midnight Oracle")) for name in visible]

    scopes = (
        ("private", BotCommandScopeAllPrivateChats()),
        ("groups", BotCommandScopeAllGroupChats()),
        ("default", None),
    )
    for label, scope in scopes:
        try:
            if scope is None:
                await app.bot.set_my_commands(commands)
            else:
                await app.bot.set_my_commands(commands, scope=scope)
            log.info("COMMAND_MENU_PUBLISHED | scope=%s | count=%d | total_live=%d", label, len(commands), len(names))
        except Exception:
            log.exception("COMMAND_MENU_PUBLISH_FAILED | scope=%s", label)

    try:
        from telegram import MenuButtonCommands
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        log.info("COMMAND_MENU_BUTTON_READY | menu=commands")
    except Exception:
        log.exception("COMMAND_MENU_BUTTON_FAILED")

    if len(names) > 100:
        log.info("COMMAND_MENU_CAPPED | total_live=%d | native_menu=%d | full_archive=help", len(names), len(commands))

    return names


def configure_lifecycle(app, storage_client, oracle_tz):
    """Attach startup automation and recovery hooks to the application."""
    async def post_init():
        log.info("BOOT_DIAGNOSTIC | post_init entered")
        live_commands = await _set_commands(app)

        from handlers.social_engine import register_jobs, init_storage
        from handlers.presence_engine import register as register_presence, silence_check
        from handlers.help_command import register as help_register
        from handlers.homecoming import homecoming_job
        from handlers import social_engine
        from handlers.oracle_governor import install as install_oracle_governor

        init_storage(storage_client)
        install_oracle_governor(social_engine)
        log.info("Oracle delivery governor installed | enabled=%s", bool(getattr(social_engine, "_governor_installed", False)))

        jq = app.job_queue
        if jq and not hasattr(jq, "run_weekly"):
            def _run_weekly(callback, time, weekday=None, days=(), name=None, data=None, job_kwargs=None):
                day = weekday if weekday is not None else (days[0] if days else 0)
                return jq.run_daily(callback, time=time, days=(day,), name=name, data=data, job_kwargs=job_kwargs)
            jq.run_weekly = _run_weekly
            log.info("Installed run_weekly compatibility adapter")

        register_jobs(app)
        register_presence(app)
        help_register(app)

        if jq:
            jq.run_repeating(homecoming_job, interval=21600, first=30, name="hidden_homecoming")
            jq.run_daily(
                silence_check,
                time=datetime.now(oracle_tz).replace(hour=2, minute=0, second=0, microsecond=0).timetz(),
                name="silence_check",
            )
            try:
                job_count = len(jq.jobs())
            except Exception:
                job_count = -1
            log.info("AUTOMATION_SCHEDULER_READY | jobs=%s | homecoming=6h | silence=02:00", job_count)
        else:
            log.error("AUTOMATION_SCHEDULER_DISABLED | JobQueue unavailable")

        if hasattr(legacy_bot, "_post_init"):
            try:
                await legacy_bot._post_init(app)
            except Exception:
                log.exception("legacy_bot._post_init failed")

        log.info("Post-init complete — Midnight Oracle is ready | live_member_commands=%d", len(live_commands))

    original_initialize = app.initialize
    hooks_ran = False

    async def initialize_with_hooks():
        nonlocal hooks_ran
        await original_initialize()
        if not hooks_ran:
            hooks_ran = True
            await post_init()

    app.initialize = initialize_with_hooks
    return app
