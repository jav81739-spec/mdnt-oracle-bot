"""Additive Phase 2-4 Telegram registrations for Midnight Oracle."""
from __future__ import annotations

import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CallbackQueryHandler, CommandHandler, InlineQueryHandler, MessageHandler, PollAnswerHandler, PollHandler, filters


def register_phase_surfaces(app) -> None:
    """Register durable world, callback, inline, and Mini App surfaces without replacing legacy handlers."""
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


async def house(update, context) -> None:
    """Open Oracle House through Telegram's Mini App WebApp button when configured."""
    url = (os.getenv("ORACLE_MINI_APP_URL") or os.getenv("MINI_APP_URL") or "").strip()
    if not url:
        await update.effective_message.reply_text("☾ Oracle House is quiet for a moment. The room will open when its window is ready.")
        return
    await update.effective_message.reply_text(
        "☾ Oracle House\n\nA quieter place for your memories, badges, group pulse and games.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Enter the House 🌙", web_app=WebAppInfo(url=url))]]),
    )
