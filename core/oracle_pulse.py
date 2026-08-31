"""Oracle Pulse: low-noise spontaneous intelligence, not a message timer."""
from __future__ import annotations

import random
import time
from .oracle_freshness import FreshnessGovernor
from .oracle_mind import generate_gossip, generate_story

CHECK_INTERVAL = 45 * 60
DELIVERY_COOLDOWN = 6 * 3600
ACTIVE_WINDOW = 6 * 3600


def _should_speak(group_id: int, active_count: int, now: float) -> bool:
    """A scheduled check is only an opportunity; Pulse decides whether to speak."""
    if active_count < 2:
        return False
    # The decision is intentionally independent of message volume. A group with a
    # little recent life gets a chance; flooding cannot force a Pulse event.
    phase = int(now // CHECK_INTERVAL)
    rng = random.Random(hash((group_id, phase, "oracle-pulse")))
    return rng.random() < 0.30


async def pulse_callback(context) -> None:
    application = context.application
    db = application.bot_data.get("oracle_db")
    if not db:
        return
    freshness = FreshnessGovernor(application)
    rows = await db.fetchall("SELECT group_id FROM group_profile")
    now = time.time()
    for row in rows:
        group_id = int(row[0])
        active = await db.fetchall("SELECT user_id FROM members WHERE group_id=? AND last_seen>? LIMIT 12", (group_id, now - ACTIVE_WINDOW))
        if not _should_speak(group_id, len(active), now):
            continue
        previous = await db.fetchone("SELECT sent_at FROM scheduled_log WHERE group_id=? AND schedule_type LIKE 'pulse:%' ORDER BY sent_at DESC LIMIT 1", (group_id,))
        if previous and now - float(previous[0]) < DELIVERY_COOLDOWN:
            continue
        # Creative material is generated independently of member memory.
        accepted = None
        for _ in range(8):
            piece = generate_story() if random.SystemRandom().random() < 0.52 else generate_gossip()
            if freshness.accept(group_id, piece.kind, piece.text, theme=piece.kind, media="none", pair="none", strategy="creative-pulse"):
                accepted = piece
                break
        if accepted is None:
            continue
        try:
            await application.bot.send_message(group_id, accepted.text, parse_mode="Markdown", disable_web_page_preview=True)
            await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)", (group_id, f"pulse:{accepted.kind}", now))
        except Exception:
            continue


def install(application) -> None:
    """Install one periodic opportunity checker; delivery remains decision-based."""
    if application.bot_data.get("_oracle_pulse_installed"):
        return
    if application.job_queue is None:
        raise RuntimeError("ORACLE_PULSE_REQUIRES_JOB_QUEUE")
    application.job_queue.run_repeating(pulse_callback, interval=CHECK_INTERVAL, first=CHECK_INTERVAL, name="oracle_pulse")
    application.bot_data["_oracle_pulse_installed"] = True
