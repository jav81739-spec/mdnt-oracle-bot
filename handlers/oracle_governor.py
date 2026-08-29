"""Central delivery governor for Midnight Oracle autonomous features.

The governor is deliberately installed by the runtime registry before
social_engine.register_jobs(). It wraps the engine's `_w` job factory rather
than replacing it with an incompatible callback signature.
"""
from __future__ import annotations

import contextvars
import logging
import os
import time

log = logging.getLogger("midnight.governor")
_ROOM_COOLDOWN = int(os.getenv("ORACLE_ROOM_COOLDOWN", "1800") or "1800")
_WILD_COOLDOWN = int(os.getenv("ORACLE_WILD_COOLDOWN", "21600") or "21600")
_pending_done = contextvars.ContextVar("oracle_pending_done", default=None)


def install(engine):
    if getattr(engine, "_governor_installed", False):
        log.debug("Oracle governor already installed")
        return

    async def check_done(key, ttl):
        """Check a feature key but defer committing it until delivery succeeds."""
        if await engine._get(key):
            return True
        pending = _pending_done.get()
        if pending is None:
            pending = set()
            _pending_done.set(pending)
        pending.add((key, ttl))
        return False

    async def governed_post(bot, chat_id, text):
        """Send a feature message and only then commit pending completion keys."""
        sent = False
        try:
            await bot.send_message(
                chat_id,
                text,
                parse_mode=engine.ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            sent = True
        except Exception:
            try:
                clean = engine.re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
                for c in ("*", "_", "`"):
                    clean = clean.replace(c, "")
                await bot.send_message(chat_id, clean, disable_web_page_preview=True)
                sent = True
            except Exception as exc:
                log.warning("AUTONOMOUS_SEND_FAILED | chat=%s | %s", chat_id, exc)

        if not sent:
            # Do NOT consume the scheduled feature occurrence on a failed send.
            _pending_done.set(None)
            return False

        pending = _pending_done.get()
        if pending:
            for key, ttl in list(pending):
                if not await engine._get(key):
                    await engine._set(key, "1", ttl=ttl)
            pending.clear()

        now = str(int(time.time()))
        await engine._set(f"oracle:last_speak:{chat_id}", now, ttl=86400 * 7)
        log.info("AUTONOMOUS_SENT | chat=%s", chat_id)
        return True

    async def room_allowed(chat_id):
        raw = await engine._get(f"oracle:last_speak:{chat_id}")
        try:
            return int(time.time()) - int(raw or 0) >= _ROOM_COOLDOWN
        except Exception:
            return True

    async def active_room(chat_id):
        raw = await engine._get(f"room:last_activity:{chat_id}")
        try:
            return bool(raw) and int(time.time()) - int(raw) <= 86400
        except Exception:
            return False

    async def run_feature(bot, fn):
        """Execute one autonomous feature against every eligible room."""
        try:
            from startup import get_broadcast_targets
            targets = await get_broadcast_targets(
                include_groups=True,
                include_channels=False,
            )
        except Exception as exc:
            log.warning("AUTONOMOUS_TARGET_DISCOVERY_FAILED | %s", exc)
            targets = []

        configured = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
        if configured and configured not in targets:
            targets.append(configured)
        targets = list(dict.fromkeys(targets))

        attempted = skipped = sent = 0
        for chat_id in targets:
            if not await room_allowed(chat_id):
                skipped += 1
                continue

            if fn.__name__ == "wild_signal":
                if not await active_room(chat_id):
                    skipped += 1
                    continue
                raw = await engine._get(f"oracle:wild_last:{chat_id}")
                try:
                    if int(time.time()) - int(raw or 0) < _WILD_COOLDOWN:
                        skipped += 1
                        continue
                except Exception:
                    pass

            attempted += 1
            before = await engine._get(f"oracle:last_speak:{chat_id}")
            try:
                await fn(bot, chat_id)
            except Exception as exc:
                log.warning(
                    "AUTONOMOUS_FEATURE_FAILED | feature=%s | chat=%s | %s",
                    fn.__name__, chat_id, exc,
                )
                continue

            after = await engine._get(f"oracle:last_speak:{chat_id}")
            if after and after != before:
                sent += 1
                if fn.__name__ == "wild_signal":
                    await engine._set(
                        f"oracle:wild_last:{chat_id}",
                        after,
                        ttl=86400,
                    )

        log.info(
            "AUTONOMOUS_RUN | feature=%s | targets=%d | attempted=%d | sent=%d | skipped=%d",
            fn.__name__, len(targets), attempted, sent, skipped,
        )

    def governed_job_factory(fn):
        """Return the PTB JobQueue callback expected by social_engine._w."""
        async def job_callback(context):
            bot = context.bot
            await run_feature(bot, fn)
        job_callback.__name__ = fn.__name__
        return job_callback

    # IMPORTANT: social_engine.register_jobs() calls `_w(feature_fn)`.
    # Therefore `_w` must remain a factory, not become a `(bot, fn)` callback.
    engine._done = check_done
    engine._post = governed_post
    engine._w = governed_job_factory
    engine._governor_installed = True
    log.info(
        "Oracle delivery governor installed | room_cooldown=%ss | wild_cooldown=%ss",
        _ROOM_COOLDOWN,
        _WILD_COOLDOWN,
    )
