"""Canonical executable entry point for Midnight Oracle.

Render and local production runs execute ``python bot.py``.  The real runtime
lives in ``midnight_oracle.main``; this file intentionally stays a tiny launcher
so there is exactly one production application construction path.
"""

from midnight_oracle.main import main


if __name__ == "__main__":
    main()
