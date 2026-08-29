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

_AUTONOMOUS_JOB_NAMES = {
    "energy_forecast", "mirror_of_day", "the_unnamed", "friction_pair",
    "midnight_wrap", "soul_thread", "shadow_scan", "constellation_map",
    "oracle_archive", "viral_pull", "signal_pair", "constellation",
    "the_chosen", "orbit_map", "glow_signal", "void_pair",
    "the_confession", "wild_signal",
}


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


def _clear_legacy_autonomous_jobs(jq):
    removed = []
    for job in list(jq.jobs()):
        name = getattr(job, "name", "")
        if name in _AUTONOMOUS_JOB_NAMES or name.startswith("oracle_autonomous:"):
            jq.scheduler.remove_job(job.id)
            removed.append(name)
    if removed:
        log.warning(
            "AUTONOMOUS_LEGACY_JOBS_REMOVED | count=%d | names=%s",
            len(removed), ",".join(removed),
        )
    return len(removed)


def configure_lifecycle(app, storage_client, oracle_tz):
    async def post_init():
        log.info("BOOT_DIAGNOSTIC | post_init entered")
        await _set_commands(app)

        from handlers.social_engine import init_storage
        from handlers.presence_engine import register as register_presence, silence_check
        from handlers.help_command import register as help_register
        from handlers.homecoming import homecoming_job
        from handlers import social_engine
        from handlers.oracle_governor import install as install_oracle_governor

        init_storage(storage_client)

        if hasattr(legacy_bot, "_post_init"):
            try:
                await legacy_bot._post_init(app)
            except Exception:
                log.exception("legacy_bot._post_init failed")

        jq = app.job_queue
        if not jq:
            log.error("AUTOMATION_SCHEDULER_DISABLED | JobQueue unavailable")
            register_presence(app)
            help_register(app)
            log.info("Post-init complete — Midnight Oracle is ready")
            return

        removed = _clear_legacy_autonomous_jobs(jq)
        log.info("AUTONOMOUS_LEGACY_CLEANUP | removed=%d", removed)

        install_oracle_governor(social_engine)
        log.info(
            "Oracle delivery governor installed | enabled=%s",
            bool(getattr(social_engine, "_governor_installed", False)),
        )

        from handlers.autonomous_scheduler import register as register_autonomous
        autonomous_count = register_autonomous(
            app,
            social_engine,
            social_engine._governed_run_feature,
            oracle_tz,
        )
        log.info("AUTOMATION_SCHEDULER_READY | autonomous_features=%d", autonomous_count)

        register_presence(app)
        help_register(app)

        jq.run_repeating(homecoming_job, interval=21600, first=30, name="hidden_homecoming")
        jq.run_daily(
            silence_check,
            time=datetime.now(oracle_tz).replace(hour=2, minute=0, second=0, microsecond=0).timetz(),
            name="silence_check",
        )

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
                "AUTOMATION_SCHEDULER_JOBS | jobs=%d | names=%s",
                len(jobs), ",".join(job_names),
            )
        except Exception:
            log.exception("Could not inspect scheduled jobs")

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
