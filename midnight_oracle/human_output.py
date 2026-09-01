"""Central public-output guard for Midnight Oracle.

Keeps internal mechanics private while allowing existing engines to remain intact.
Only presentation is normalized; the conversation brain is not replaced.
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Awaitable, Callable

from .generators.social_voice import voice

log = logging.getLogger("midnight.human_output")

_INSTALLED = False


def _wrap_post(module: Any, attr: str, label: str) -> None:
    original = getattr(module, attr, None)
    if not callable(original) or getattr(original, "_midnight_humanized", False):
        return

    @functools.wraps(original)
    async def wrapped(bot, chat_id, text, *args, **kwargs):
        rendered = await voice.render(
            str(text or ""),
            context=f"Telegram group; public {label} moment",
            event_key=f"public:{label}:{chat_id}",
        )
        return await original(bot, chat_id, rendered or text, *args, **kwargs)

    wrapped._midnight_humanized = True
    setattr(module, attr, wrapped)


def install() -> None:
    """Install presentation guards once; failures never break startup."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    for module_name, attr, label in (
        ("handlers.social_engine", "_post", "social"),
        ("handlers.presence_engine", "_post", "presence"),
    ):
        try:
            module = __import__(module_name, fromlist=[attr])
            _wrap_post(module, attr, label)
        except Exception:
            log.exception("HUMAN_OUTPUT_INSTALL_FAILED | module=%s", module_name)
