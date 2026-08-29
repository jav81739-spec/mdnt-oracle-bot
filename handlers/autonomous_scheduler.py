"""Canonical autonomous scheduler for Midnight Oracle.

This deliberately does not monkey-patch social_engine._w. Jobs are created
through one explicit callback path so APScheduler -> governor -> feature ->
Telegram delivery is observable and failure-isolated.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("midnight.autonomous")


def _time(tz: ZoneInfo, hour: int, minute: int = 0):
    return datetime.now(tz).replace(hour=hour, minute=minute, second=0, microsecond=0).timetz()


def register(app, engine, governor_run_feature, oracle_tz: ZoneInfo):
    jq = app.job_queue
    if not jq:
        log.error("AUTOMATION_SCHEDULER_DISABLED | reason=job_queue_unavailable")
        return 0

    def job(fn):
        async def callback(context):
            log.info("AUTONOMOUS_JOB_ENTERED | feature=%s", fn.__name__)
            try:
                await governor_run_feature(context.bot, fn)
            except Exception:
                log.exception("AUTONOMOUS_JOB_FAILED | feature=%s", fn.__name__)
        callback.__name__ = fn.__name__
        return callback

    # The governor owns targeting, cooldowns, successful-send accounting and
    # failure isolation. The scheduler only owns timing.
    daily = [
        (engine.energy_forecast, 7, 0, "energy_forecast"),
        (engine.mirror_of_day, 0, 7, "mirror_of_day"),
        (engine.the_unnamed, 2, 22, "the_unnamed"),
        (engine.friction_pair, 18, 6, "friction_pair"),
        (engine.midnight_wrap, 23, 59, "midnight_wrap"),
    ]
    for fn, h, m, name in daily:
        jq.run_daily(job(fn), time=_time(oracle_tz, h, m), name=name)

    weekly = [
        (engine.soul_thread, 23, 11, 0, "soul_thread"),
        (engine.shadow_scan, 22, 0, 3, "shadow_scan"),
        (engine.constellation_map, 20, 0, 5, "constellation_map"),
        (engine.oracle_archive, 21, 30, 2, "oracle_archive"),
        (engine.viral_pull, 21, 0, 6, "viral_pull"),
    ]
    for fn, h, m, weekday, name in weekly:
        if hasattr(jq, "run_weekly"):
            jq.run_weekly(job(fn), time=_time(oracle_tz, h, m), weekday=weekday, name=name)
        else:
            jq.run_daily(job(fn), time=_time(oracle_tz, h, m), days=(weekday,), name=name)

    repeating = [
        (engine.signal_pair, 86400 * 3, 60, "signal_pair"),
        (engine.constellation, 86400 * 5, 120, "constellation"),
        (engine.the_chosen, 86400 * 2, 180, "the_chosen"),
        (engine.orbit_map, 86400 * 4, 240, "orbit_map"),
        (engine.glow_signal, 86400 * 3, 300, "glow_signal"),
        (engine.void_pair, 21600, 360, "void_pair"),
        (engine.the_confession, 14400, 420, "the_confession"),
        (engine.wild_signal, 3600, 480, "wild_signal"),
    ]
    for fn, interval, first, name in repeating:
        jq.run_repeating(job(fn), interval=interval, first=first, name=name)

    count = len(daily) + len(weekly) + len(repeating)
    log.info("AUTOMATION_SCHEDULER_REGISTERED | autonomous_features=%d", count)
    return count
