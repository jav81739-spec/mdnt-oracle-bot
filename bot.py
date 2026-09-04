"""Canonical executable entry point for Midnight Oracle.

The production application is built by ``midnight_oracle.main``. This module
keeps the historical production-entrypoint contracts that the runtime and
regression suite rely on, without importing the obsolete monolithic legacy
runner or starting any service merely by importing it.
"""
from __future__ import annotations

import asyncio
import logging
import os
from types import SimpleNamespace

import startup
from telegram.ext import Application, ContextTypes

from handlers import deathgames_v2
from midnight_oracle.main import (
    _post_init,
    _post_shutdown,
    build_application as _canonical_build_application,
)
from storage import redis_client

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger("midnight.entrypoint")
legacy_bot = SimpleNamespace(deathgames=deathgames_v2)


async def _error(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compatibility error hook; report failures without leaking user data."""
    log.error("MIDNIGHT_RUNTIME_ERROR | error=%r", context.error)


def build_application() -> Application:
    """Return the canonical application with the production error hook."""
    application = _canonical_build_application()
    application.add_error_handler(_error)
    return application


def main() -> None:
    """Run the canonical startup manager exactly once."""
    log.info(
        "RUNTIME_IDENTITY | branch=%s | commit=%s | pid=%s | entrypoint=canonical | source=midnight_oracle.main",
        os.getenv("RENDER_GIT_BRANCH", os.getenv("GIT_BRANCH", "unknown")),
        os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", "unknown")),
        os.getpid(),
    )
    asyncio.run(startup.run(build_application(), redis_client))


if __name__ == "__main__":
    main()
