"""Oracle Pulse: decision-based spontaneous presence for Midnight Oracle."""
from __future__ import annotations

import time

from .oracle_freshness import FreshnessGovernor
from .oracle_mind import generate_contextual_piece
from .oracle_presence import decide_presence

CHECK_INTERVAL = 15 * 60
DELIVERY_COOLDOWN = 3 * 3600
ACTIVE_WINDOW = 6 * 3600


async def pulse_callback(context) -> None:
    application = context.application
    db = application.bot_data.get("oracle_db")
    if not db:
        return

    freshness = FreshnessGovernor(application)
    atmosphere = application.bot_data.get("oracle_atmosphere", {})
    rows = await db.fetchall("SELECT group_id FROM group_profile")
    now = time.time()

    for row in rows:
        group_id = int(row[0])
        active = await db.fetchall(
            "SELECT user_id FROM members WHERE group_id=? AND last_seen>? LIMIT 12",
            (group_id, now - ACTIVE_WINDOW),
        )
        items = list(atmosphere.get(str(group_id), []))[-8:]
        previous = await db.fetchone(
            "SELECT sent_at FROM scheduled_log WHERE group_id=? AND schedule_type LIKE 'pulse:%' ORDER BY sent_at DESC LIMIT 1",
            (group_id,),
        )
        last_delivery = float(previous[0]) if previous else None
        decision = decide_presence(
            group_id=group_id,
            now=now,
            active_count=len(active),
            context_items=items,
            last_delivery=last_delivery,
            cooldown_seconds=DELIVERY_COOLDOWN,
        )
        if not decision.speak:
            continue

        accepted = None
        for attempt in range(6):
            piece = await generate_contextual_piece(
                items,
                seed=f"{group_id}:{int(now // CHECK_INTERVAL)}:{decision.strategy}:{attempt}",
            )
            if freshness.accept(
                group_id,
                piece.kind,
                piece.text,
                theme=decision.reason,
                media="none",
                pair="none",
                strategy=decision.strategy,
            ):
                accepted = piece
                break
        if accepted is None:
            continue

        try:
            # Generated text is untrusted Markdown. Plain text prevents an otherwise
            # successful Oracle decision from becoming a Telegram parse failure.
            await application.bot.send_message(
                group_id,
                accepted.text,
                disable_web_page_preview=True,
            )
            await db.execute(
                "INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)",
                (group_id, f"pulse:{accepted.kind}", now),
            )
        except Exception:
            continue


def install(application) -> None:
    """Install one lightweight opportunity checker; Pulse decides delivery itself."""
    if application.bot_data.get("_oracle_pulse_installed"):
        return
    if application.job_queue is None:
        raise RuntimeError("ORACLE_PULSE_REQUIRES_JOB_QUEUE")
    application.job_queue.run_repeating(
        pulse_callback,
        interval=CHECK_INTERVAL,
        first=60,
        name="oracle_pulse",
    )
    application.bot_data["_oracle_pulse_installed"] = True
