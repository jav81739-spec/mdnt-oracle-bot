# Verified command menu patch

This branch changes only `bot.py`.

- Registers existing aesthetic Oracle handlers when they are not already registered.
- Builds Telegram command menus from commands that are actually registered.
- Keeps `/announce`, `/broadcast`, and `/midnightmap` owner-only in the owner-specific menu when those handlers are registered.
- Removes the previous hard-coded assumption that the 21-command list represented the full working command set.
- Does not modify legacy handler implementations.
