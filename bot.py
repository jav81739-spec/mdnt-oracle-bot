"""Midnight Oracle — canonical production entrypoint."""
from __future__ import annotations

import asyncio
import logging

import startup
try:
    from storage import redis_client as _storage_client
except Exception:
    _storage_client = None
from midnight_oracle.main import build_application as _build_application

log = logging.getLogger("midnight.entrypoint")


def build_application():
    """Build the repaired canonical application exactly once."""
    return _build_application()


async def _run():
    app = build_application()
    startup.init(_storage_client)
    await startup.run(app, storage_client=_storage_client)


def main() -> None:
    """Start the single canonical polling process with the existing lease manager."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
