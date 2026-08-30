"""Midnight Oracle runtime compatibility bootstrap.

Keeps the existing Social Engine intact while wiring its autonomous jobs,
member registry, and canonical human-chat router into the live application.
No commands are replaced and no autonomous feature names are exposed.
"""
from __future__ import annotations

import asyncio
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
                if info.get("type") in ("group", "supergroup"):
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

    _se._w = _fanout

    import startup as _startup
    _original_run = _startup.run

    async def _runtime_run(application, storage_client=None):
        original_post_init = application.post_init

        async def _post_init_with_runtime(app):
            if original_post_init is not None:
                await original_post_init(app)

            try:
                _se.init_storage(storage_client)
                _se.register_jobs(app)
                log.info("AUTONOMOUS_SOCIAL_ENGINE_READY | scheduled=19 | registry_fanout=on")
            except Exception:
                log.exception("AUTONOMOUS_SOCIAL_ENGINE_START_FAILED")

            try:
                from telegram.ext import MessageHandler, filters
                marker = "_midnight_human_router_registered"
                if not app.bot_data.get(marker):
                    router = app.bot_data.get("oracle_router")
                    if router is not None:
                        app.add_handler(
                            MessageHandler(filters.TEXT & ~filters.COMMAND, router.handle),
                            group=-40,
                        )
                        app.bot_data[marker] = True
                        log.info("HUMAN_CHAT_ROUTER_READY | group=on")
            except Exception:
                log.exception("HUMAN_CHAT_ROUTER_REGISTRATION_FAILED")

            try:
                from telegram.ext import MessageHandler, filters
                marker = "_midnight_social_member_tracker_registered"
                if not app.bot_data.get(marker):
                    app.add_handler(
                        MessageHandler(filters.ChatType.GROUPS, _se.track_member),
                        group=-39,
                    )
                    app.bot_data[marker] = True
                    log.info("SOCIAL_MEMBER_REGISTRY_READY")
            except Exception:
                log.exception("SOCIAL_MEMBER_TRACKER_REGISTRATION_FAILED")

        application.post_init = _post_init_with_runtime
        return await _original_run(application, storage_client=storage_client)

    _startup.run = _runtime_run
    log.info("Midnight runtime bootstrap installed | social fanout=on | live chat bridge=on")
except Exception:
    log.exception("Midnight runtime bootstrap could not be installed")
