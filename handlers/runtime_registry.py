"""Canonical Telegram handler/lifecycle registry for Midnight Oracle."""
from __future__ import annotations

import logging
from datetime import datetime

from telegram import BotCommand
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
    app = Application.builder().token(token).build()

    async def chat_registry(update, context):
        chat_obj = getattr(update, "effective_chat", None)
        if chat_obj and chat_obj.type in ("group", "supergroup", "channel"):
            from startup import register_chat
            await register_chat(chat_obj.id, chat_obj.type, chat_obj.title or "")

    app.add_handler(MessageHandler(filters.ALL, chat_registry), group=-999)

    from handlers.engagement_engine import init_storage as init_engagement_storage, register as register_engagement
    init_engagement_storage(storage_client)
    register_engagement(app)

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
        from handlers.midnightmap import register as register_midnightmap
        register_midnightmap(app)
    except Exception:
        log.exception("midnightmap registration failed")

    return app


def _shim_register(app):
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
            module.register(app)

    if hasattr(legacy_bot, "handle_ai_message"):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, legacy_bot.handle_ai_message), group=10)
    sticker_handler = getattr(legacy_bot, "handle_sticker", None) or getattr(legacy_bot, "smart_sticker_reply", None)
    if sticker_handler:
        app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))


async def _set_commands(app):
    commands = [
        BotCommand("oracle", "🔮 Get a reading"), BotCommand("aura", "🟣 Scan your aura"),
        BotCommand("vibecheck", "✨ Check your vibe"), BotCommand("identity", "🃏 Your archetype"),
        BotCommand("shadow", "🌑 Meet your shadow"), BotCommand("element", "🌌 Your cosmic element"),
        BotCommand("corecode", "🔱 Your core words"), BotCommand("universe", "🌌 A message"),
        BotCommand("ritual", "🕯️ Today's ritual"), BotCommand("duality", "☯️ Your two sides"),
        BotCommand("nightreport", "🌙 Night report"), BotCommand("sigil", "🔱 Your sigil"),
        BotCommand("glitch", "⚡ Oracle glitch"), BotCommand("checkin", "🌙 Daily check-in"),
        BotCommand("streakcheck", "📊 Check streak"), BotCommand("vent", "🫀 Anonymous vent"),
        BotCommand("coinboard", "🏆 Coin leaderboard"), BotCommand("cgift", "💝 Gift coins"),
        BotCommand("rob", "🦹 Rob coins"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        log.info("Telegram command menu set | public_commands=%d", len(commands))
    except Exception:
        log.exception("Could not set command menu")


def configure_lifecycle(app, storage_client, oracle_tz):
    async def post_init():
        log.info("BOOT_DIAGNOSTIC | post_init entered")
        await _set_commands(app)

        from handlers.social_engine import register_jobs, init_storage
        from handlers.presence_engine import register as register_presence, silence_check
        from handlers.help_command import register as help_register
        from handlers.homecoming import homecoming_job
        from handlers import social_engine
        from handlers.oracle_governor import install as install_oracle_governor

        init_storage(storage_client)
        install_oracle_governor(social_engine)
        log.info(
            "Oracle delivery governor installed | enabled=%s",
            bool(getattr(social_engine, "_governor_installed", False)),
        )

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

            # Non-user-facing scheduler smoke test. This fires once shortly after
            # startup and proves that APScheduler can invoke an async callback.
            async def oracle_scheduler_probe(context):
                log.info(
                    "AUTONOMOUS_SCHEDULER_PROBE | callback=entered | governor=%s",
                    bool(getattr(social_engine, "_governor_installed", False)),
                )

            jq.run_once(oracle_scheduler_probe, when=10, name="oracle_scheduler_probe")

            try:
                jobs = list(jq.jobs())
                job_names = [getattr(j, "name", "?") for j in jobs]
                log.info(
                    "AUTOMATION_SCHEDULER_READY | jobs=%d | homecoming=6h | silence=02:00 | names=%s",
                    len(jobs), ",".join(job_names),
                )
            except Exception:
                log.exception("Could not inspect scheduled jobs")
        else:
            log.error("AUTOMATION_SCHEDULER_DISABLED | JobQueue unavailable")

        if hasattr(legacy_bot, "_post_init"):
            try:
                await legacy_bot._post_init(app)
            except Exception:
                log.exception("legacy_bot._post_init failed")

        log.info("Post-init complete — Midnight Oracle is ready")

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
