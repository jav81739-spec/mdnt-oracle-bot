"""Production-safe Telegram error handling for Midnight Oracle."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.error import Conflict, Forbidden, RetryAfter

log = logging.getLogger("midnight.telegram")


async def handle_telegram_error(update: object, context) -> None:
    """Catch handler exceptions so one bad update never becomes an unhandled error.

    The handler deliberately avoids echoing exception details to users. Telegram
    API errors are logged with useful context, while the update loop is allowed
    to continue whenever python-telegram-bot can safely do so.
    """
    error = getattr(context, "error", None)
    update_id = getattr(update, "update_id", None)
    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    chat_id = getattr(chat, "id", None)
    user_id = getattr(user, "id", None)

    if isinstance(error, Conflict):
        log.error(
            "Telegram polling conflict update=%s chat=%s user=%s; "
            "the process-level polling lease should prevent duplicate pollers",
            update_id, chat_id, user_id,
        )
        return

    if isinstance(error, RetryAfter):
        log.warning(
            "Telegram rate limit update=%s chat=%s retry_after=%ss",
            update_id, chat_id, error.retry_after,
        )
        return

    if isinstance(error, Forbidden):
        log.info(
            "Telegram forbidden update=%s chat=%s user=%s: %s",
            update_id, chat_id, user_id, error,
        )
        return

    log.exception(
        "Unhandled Telegram update exception update=%s chat=%s user=%s",
        update_id, chat_id, user_id,
        exc_info=error,
    )


def install_error_handler(application) -> None:
    """Install the handler once, without disturbing existing handlers."""
    marker = "_midnight_error_handler_installed"
    if getattr(application, marker, False):
        return
    application.add_error_handler(handle_telegram_error)
    setattr(application, marker, True)
    log.info("TELEGRAM_ERROR_HANDLER installed")
