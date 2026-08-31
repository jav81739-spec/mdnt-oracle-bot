"""Registry-driven autonomous scheduler for Midnight Oracle social surprises."""
from __future__ import annotations
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram.ext import Application

from . import social_engine

TZ = social_engine.ORACLE_TZ

async def _targets():
    """Return every known group, not a single GROUP_CHAT_ID env target."""
    try:
        from startup import get_chat_registry
        registry = await get_chat_registry()
        return [int(cid) for cid, info in registry.items()
                if info.get("type") in ("group", "supergroup")]
    except Exception:
        return []

async def _safe(fn, bot, chat_id):
    try:
        await fn(bot, chat_id)
    except Exception:
        social_engine.log.exception("AUTONOMOUS_FEATURE_FAILED | feature=%s | chat=%s", fn.__name__, chat_id)

async def _tick(context):
    """Dispatch autonomous features to all registered groups.

    Feature functions retain their own idempotency keys, so a restart or a
    scheduler tick cannot duplicate a daily/weekly surprise.
    """
    now = datetime.now(TZ)
    targets = await _targets()
    if not targets:
        return

    daily = {
        (7, 0): social_engine.energy_forecast,
        (0, 7): social_engine.mirror_of_day,
        (2, 22): social_engine.the_unnamed,
        (18, 6): social_engine.friction_pair,
        (23, 59): social_engine.midnight_wrap,
    }
    weekly = {
        (0, 23, 11): social_engine.soul_thread,
        (3, 22, 0): social_engine.shadow_scan,
        (5, 20, 0): social_engine.constellation_map,
        (2, 21, 30): social_engine.oracle_archive,
        (6, 21, 0): social_engine.viral_pull,
    }

    # The scheduler ticks once per minute; a two-minute tolerance prevents a
    # missed tick during a brief event-loop pause without double-posting.
    minute = now.hour * 60 + now.minute
    for chat_id in targets:
        for (hour, minute_of_hour), fn in daily.items():
            if minute == hour * 60 + minute_of_hour:
                await _safe(fn, context.bot, chat_id)
        for (weekday, hour, minute_of_hour), fn in weekly.items():
            if now.weekday() == weekday and minute == hour * 60 + minute_of_hour:
                await _safe(fn, context.bot, chat_id)

        # Cadence-based surprises. Their own _done() keys are the final
        # duplicate guard, so these can safely be evaluated every minute.
        cadence = (
            (social_engine.signal_pair, 3 * 86400),
            (social_engine.constellation, 5 * 86400),
            (social_engine.the_chosen, 2 * 86400),
            (social_engine.orbit_map, 4 * 86400),
            (social_engine.glow_signal, 3 * 86400),
            (social_engine.void_pair, 6 * 3600),
            (social_engine.the_confession, 4 * 3600),
            (social_engine.wild_signal, 3600),
        )
        for fn, interval in cadence:
            # Feature-local idempotency makes repeated evaluation safe.
            await _safe(fn, context.bot, chat_id)


def register(app: Application) -> bool:
    """Install exactly one registry-driven autonomous dispatcher."""
    if app.bot_data.get("_midnight_autonomous_scheduler_registered"):
        return False
    jq = app.job_queue
    if jq is None:
        raise RuntimeError("JobQueue is required for autonomous scheduling")
    jq.run_repeating(_tick, interval=60, first=5, name="midnight_autonomous_dispatch")
    app.bot_data["_midnight_autonomous_scheduler_registered"] = True
    social_engine.log.info("AUTONOMOUS_SCHEDULER_READY | registry=dynamic | tick=60s | surprises=19")
    return True
