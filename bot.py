"""Midnight Oracle production entrypoint.

The legacy monolith is preserved as ``legacy_bot.py`` during the staged rebuild.
New core services are loaded through the compatibility storage facade, while the
entrypoint stays tiny so the active surface is obvious and testable.
"""

from legacy_bot import main


if __name__ == "__main__":
    main()
