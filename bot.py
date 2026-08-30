"""Midnight Oracle — canonical production entrypoint.

The repaired Phase 1–5 runtime lives in ``midnight_oracle.main``.  The root
entrypoint must launch that runtime directly; delegating to the legacy runtime
bypassed the repaired engine and left Telegram with the wrong handler stack.
"""
from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

import startup
from midnight_oracle.main import build_application as _build_application

log = logging.getLogger("midnight.entrypoint")


def _command_names(app):
    names = set()
    for handlers in getattr(app, "handlers", {}).values():
        for handler in handlers:
            for command in (getattr(handler, "commands", None) or ()):
                name = str(command).strip().lstrip("/").casefold()
                if name:
                    names.add(name)
    return names


async def _publish_commands(app):
    """Publish every command actually registered by the canonical runtime."""
    names = sorted(name for name in _command_names(app) if len(name) <= 32)
    commands = [BotCommand(name, "Midnight Oracle") for name in names]
    if not commands:
        raise RuntimeError("Canonical runtime registered zero Telegram commands")

    await app.bot.set_my_commands(commands)
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
    log.info("COMMANDS_READY | count=%d | names=%s", len(commands), ",".join(names))


async def _post_init(app):
    """Run the canonical Phase 1–5 initializer, then verify command registration."""
    # midnight_oracle.main installs its own post_init during build_application().
    canonical_post_init = app.post_init
    if canonical_post_init is not None:
        await canonical_post_init(app)
    await _publish_commands(app)
    log.info("PRODUCTION_RUNTIME_READY | phase1_5=on | commands=on | chat=on | groups=on")


def build_application():
    """Build the repaired canonical application exactly once."""
    app = _build_application()
    app.post_init = _post_init
    return app


async def _run():
    app = build_application()
    await startup.run(app)


def main() -> None:
    """Start the single canonical polling process with the existing lease manager."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
