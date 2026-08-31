"""Canonical executable entry point for Midnight Oracle.

The production application is built by ``midnight_oracle.main``.  This module
keeps the historical production-entrypoint contracts that the runtime and
regression suite rely on, without starting any service merely by importing it.
"""
from __future__ import annotations

import legacy_bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes

from handlers import deathgames_v2 as _deathgames_v2
from midnight_oracle.main import (
    _post_init,
    _post_shutdown,
    build_application as _canonical_build_application,
    main as _canonical_main,
)

legacy_bot.deathgames = _deathgames_v2


async def _error(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compatibility error hook; report through the application's logger."""
    log = getattr(getattr(context, "application", None), "logger", None)
    if log is not None:
        log.exception("MIDNIGHT_RUNTIME_ERROR", exc_info=context.error)


def build_application() -> Application:
    """Return the canonical application with the production error hook."""
    application = _canonical_build_application()
    application.add_error_handler(_error)
    return application


def main() -> None:
    """Run the canonical startup manager exactly once."""
    _canonical_main()


if __name__ == "__main__":
    main()
