"""Midnight Oracle compatibility bootstrap.

The canonical startup manager owns application lifecycle and handler
registration. This module only supplies the legacy Social Engine's dynamic
fan-out wrapper; it must never monkey-patch startup.run or application.post_init.
"""
from __future__ import annotations

import logging

log = logging.getLogger("midnight.runtime")

try:
    from handlers import social_engine as _se

    async def _known_targets() -> list[int]:
        targets: set[int] = set()
        if _se.GROUP_CHAT_ID:
            targets.add(int(_se.GROUP_CHAT_ID))
        try:
            import startup
            registry = await startup.get_chat_registry()
            for cid, info in registry.items():
                if not isinstance(info, dict) or info.get("type") not in ("group", "supergroup"):
                    continue
                try:
                    targets.add(int(cid))
                except (TypeError, ValueError):
                    continue
        except Exception as exc:
            log.debug("Could not read chat registry: %s", exc)
        return sorted(targets)

    def _fanout(fn):
        async def job(ctx):
            targets = await _known_targets()
            if not targets:
                log.info("AUTONOMOUS %s skipped: no known group targets", fn.__name__)
                return
            for chat_id in targets:
                await _se._run(ctx.bot, chat_id, fn)
        return job

    # Preserve dynamic multi-group fan-out without wrapping the canonical
    # startup lifecycle. startup.run() now installs all runtime surfaces once.
    _se._w = _fanout
    log.info("Midnight runtime compatibility installed | social fanout=on | lifecycle=canonical")
except Exception:
    log.exception("Midnight runtime compatibility could not be installed")
