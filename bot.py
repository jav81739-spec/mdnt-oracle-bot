"""Canonical executable entry point for Midnight Oracle.

The production application is built by ``midnight_oracle.main``.  This module
keeps the historical production-entrypoint contracts that the runtime and
regression suite rely on, without starting any service merely by importing it.
"""
from __future__ import annotations

import asyncio
import legacy_bot
import logging
import os
import startup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes

from handlers import deathgames_v2 as _deathgames_v2
from midnight_oracle.handlers.phase_registry import register_phase_surfaces
from midnight_oracle.main import (
    _post_init,
    _post_shutdown,
    build_application as _canonical_build_application,
)
from storage import redis_client

log = logging.getLogger("midnight.entrypoint")
legacy_bot.deathgames = _deathgames_v2


async def _error(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compatibility error hook; report through the application's logger."""
    log_obj = getattr(getattr(context, "application", None), "logger", None)
    if log_obj is not None:
        log_obj.exception("MIDNIGHT_RUNTIME_ERROR", exc_info=context.error)


def build_application() -> Application:
    """Return the canonical application with the production error hook."""
    application = _canonical_build_application()
    application.add_error_handler(_error)
    return application


def main() -> None:
    """Run the canonical startup manager exactly once."""
    log.info(
        "RUNTIME_IDENTITY | branch=main | commit=%s | pid=%s | entrypoint=canonical | source=midnight_oracle.main",
        os.getenv("RENDER_GIT_COMMIT", "unknown"),
        os.getpid(),
    )
    asyncio.run(startup.run(build_application(), redis_client))


if __name__ == "__main__":
    main()
