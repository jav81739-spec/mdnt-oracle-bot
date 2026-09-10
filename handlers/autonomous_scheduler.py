"""Registry-driven autonomous scheduler for Midnight Oracle social surprises."""
from __future__ import annotations
from datetime import datetime
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
        social_engine.log.exception(
            "AUTONOMOUS_FEATURE_FAILED | feature=%s | chat=%s",
            fn.__name__, chat_id,
        )


async def _govern(chat_id: int, feature: str, priority: str = "normal") -> bool:
    """Decide whether Midnight should speak, instead of blindly firing a schedule."""
    members = await social_engine._members(chat_id)
    if len(members) < 2:
        return False

    now = int(datetime.now(TZ).timestamp())
    recent_30m = sum(1 for m in members if now - int(m.get("last", 0)) <= 1800)
    recent_6h = sum(1 for m in members if now - int(m.get("last", 0)) <= 21600)

    # Hard anti-spam gate: one autonomous post per group per 30 minutes.
    last = await social_engine._get(f"oracle:govern:last:{chat_id}")
    if last:
        try:
            if now - int(last) < 1800:
                return False
        except (TypeError, ValueError):
            pass

    # Don't manufacture conversation in a genuinely dead room.
    if recent_6h == 0 and priority != "anchor":
        return False

    # If the room is very active, let the conversation breathe unless the
    # event is an intentional time anchor (morning/evening/midnight).
    if recent_30m >= 12 and priority == "normal":
        return False

    # Record the decision, not every candidate check.
    await social_engine._set(f"oracle:govern:last:{chat_id}", str(now), ttl=86400 * 2)
    await social_engine._set(
        f"oracle:govern:feature:{chat_id}",
        feature,
        ttl=86400 * 2,
    )
    return True


async def _tick(context):
    """Dispatch autonomous features to all registered groups.

    Feature functions retain their own Redis idempotency keys. The dispatcher
    itself is time-aligned, so a deployment/restart does not fire every
    cadence immediately and flood a group.
    """
    now = datetime.now(TZ)
    targets = await _targets()
    if not targets:
        return

    minute = now.hour * 60 + now.minute
    daily = {
        (7, 0): social_engine.energy_forecast,
        (0, 7): social_engine.mirror_of_day,
        (2, 22): social_engine.the_unnamed,
        (18, 6): social_engine.friction_pair,
        (23, 59): social_engine.midnight_wrap,
        (21, 17): social_engine.midnight_story,
        (22, 47): social_engine.oracle_gossip,
    }
    weekly = {
        (0, 23, 11): social_engine.soul_thread,
        (3, 22, 0): social_engine.shadow_scan,
        (5, 20, 0): social_engine.constellation_map,
        (2, 21, 30): social_engine.oracle_archive,
        (6, 21, 0): social_engine.viral_pull,
    }

    for chat_id in targets:
        if (now.hour, now.minute) in daily:
            fn = daily[(now.hour, now.minute)]
            priority = "anchor" if fn in (
                social_engine.energy_forecast,
                social_engine.midnight_wrap,
                social_engine.midnight_story,
            ) else "normal"
            if await _govern(chat_id, fn.__name__, priority):
                await _safe(fn, context.bot, chat_id)

        weekly_key = (now.weekday(), now.hour, now.minute)
        if weekly_key in weekly:
            fn = weekly[weekly_key]
            if await _govern(chat_id, fn.__name__, "normal"):
                await _safe(fn, context.bot, chat_id)

        # Interval features are anchored to Unix time. This prevents the
        # scheduler's startup time from becoming the cadence origin.
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
        epoch = int(now.timestamp())
        for fn, interval in cadence:
            # One-minute tick window is safe because the dispatcher itself is unique.
            if epoch % interval < 60 and await _govern(chat_id, fn.__name__, "normal"):
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
    social_engine.log.info(
        "AUTONOMOUS_SCHEDULER_READY | registry=dynamic | tick=60s | surprises=19"
    )
    return True
