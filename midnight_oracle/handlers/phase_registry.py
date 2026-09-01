"""Additive Phase 2-4 Telegram registrations for Midnight Oracle."""
from __future__ import annotations

import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CallbackQueryHandler, CommandHandler, InlineQueryHandler, MessageHandler, PollAnswerHandler, PollHandler, filters


def register_phase_surfaces(app) -> None:
    """Register live legacy commands first, then durable world and Mini App surfaces."""
    try:
        import legacy_bot as _legacy_bot
        from handlers import deathgames_v2 as _deathgames_v2
        _legacy_bot.deathgames = _deathgames_v2
    except Exception:
        import logging
        logging.getLogger("midnight.phase_registry").exception("DEATHGAMES_V2_BIND_FAILED")

    try:
        from handlers.legacy_surface import register_legacy_surface
        result = register_legacy_surface(app)
        log_added = len(result.get("added", [])) if isinstance(result, dict) else -1
        log_skipped = len(result.get("skipped", [])) if isinstance(result, dict) else -1
        import logging
        logging.getLogger("midnight.phase_registry").info("LEGACY_SURFACE_WIRED | added=%s | skipped=%s", log_added, log_skipped)
    except Exception:
        import logging
        logging.getLogger("midnight.phase_registry").exception("LEGACY_SURFACE_WIRING_FAILED")

    # Relationship commands with visible, human-style output own these names.
    # Register them before the legacy compatibility surface so the old canned
    # bond/matchmaker wording can never become the live callback.
    try:
        from handlers.organic_relationships import bond, randomship, matchmaker
        existing = {
            str(command).lower().lstrip("/")
            for handlers in getattr(app, "handlers", {}).values()
            for handler in handlers
            for command in (getattr(handler, "commands", None) or ())
        }
        for command, callback in (("bond", bond), ("randomship", randomship), ("matchmaker", matchmaker)):
            if command not in existing:
                app.add_handler(CommandHandler(command, callback), group=-26)
    except Exception:
        import logging
        logging.getLogger("midnight.relationship").exception("ORGANIC_RELATIONSHIP_SURFACE_FAILED")

    try:
        existing = {
            str(command).lower().lstrip("/")
            for handlers in getattr(app, "handlers", {}).values()
            for handler in handlers
            for command in (getattr(handler, "commands", None) or ())
        }
        if "ship" not in existing:
            from handlers.friendship import ship
            app.add_handler(CommandHandler("ship", ship), group=-25)
    except Exception:
        import logging
        logging.getLogger("midnight.phase_registry").exception("SHIP_REGISTRATION_FAILED")

    from .world_handler import start_game, game_callback, handle_game_message, handle_poll_answer, handle_poll
    from .callback_handler import handle_callback
    from .inline_handler import handle_inline
    from .prediction_handler import predict, predictions

    for command in ("tod", "wyr", "nhie", "scramble"):
        app.add_handler(CommandHandler(command, start_game), group=-30)
    app.add_handler(CommandHandler("predict", predict), group=-30)
    app.add_handler(CommandHandler("predictions", predictions), group=-30)
    app.add_handler(PollAnswerHandler(handle_poll_answer), group=-30)
    app.add_handler(PollHandler(handle_poll), group=-30)
    app.add_handler(CallbackQueryHandler(game_callback, pattern=r"^game:"), group=-30)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(?:reveal_|secret:).+"), group=-29)
    app.add_handler(InlineQueryHandler(handle_inline), group=-30)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_message), group=-29)
    app.add_handler(CommandHandler("house", house), group=-30)


def house(update, context) -> None:
    """Open Oracle House through Telegram's Mini App WebApp button when configured."""
    url = (os.getenv("ORACLE_MINI_APP_URL") or os.getenv("MINI_APP_URL") or "").strip()
    if not url:
        return context.application.create_task(update.effective_message.reply_text("☾ Oracle House is quiet for a moment. The room will open when its window is ready."))
    return context.application.create_task(update.effective_message.reply_text(
        "☾ Oracle House\n\nA quieter place for your memories, badges, group pulse and games.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Enter the House 🌙", web_app=WebAppInfo(url=url))]]),
    ))
