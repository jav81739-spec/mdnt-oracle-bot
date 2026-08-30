"""Midnight Oracle — single production bridge.

The production entrypoint deliberately stays thin. The established runtime owns
Telegram handler registration and polling; this module only exposes compatibility
hooks and activates the V2 death-games implementation before startup.
"""
from __future__ import annotations

import legacy_bot
from handlers import deathgames_v2 as _deathgames_v2

_ready_state = {"ready": False}

_addcoins = legacy_bot._addcoins
_generate_gemini = legacy_bot._generate_gemini
_start_dummy_server = legacy_bot._start_dummy_server
_start_health_server = legacy_bot._start_dummy_server
_legacy_post_init = legacy_bot._post_init

legacy_bot.deathgames = _deathgames_v2


async def _post_init(app):
    """Run the established startup hook and publish readiness for health checks."""
    await _legacy_post_init(app)
    _ready_state["ready"] = True


legacy_bot._post_init = _post_init


def main():
    """Delegate production startup to the established runtime exactly once."""
    return legacy_bot.main()


if __name__ == "__main__":
    main()
