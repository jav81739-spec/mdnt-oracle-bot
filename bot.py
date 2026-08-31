"""Canonical executable entry point for Midnight Oracle."""
from __future__ import annotations

# Compatibility bridge for the legacy runtime surface. The production
# application is still constructed by midnight_oracle.main; importing the
# legacy module here must not start a second service.
import legacy_bot
from handlers import deathgames_v2 as _deathgames_v2
from midnight_oracle.main import main

legacy_bot.deathgames = _deathgames_v2


if __name__ == "__main__":
    main()
