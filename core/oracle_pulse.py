"""Low-noise Oracle Pulse: original gossip and fiction, never member gossip."""
from __future__ import annotations
import random
import time
from .oracle_freshness import FreshnessGovernor
from .oracle_mind import generate_gossip, generate_story

async def pulse_callback(context) -> None:
    application = context.application
    db = application.bot_data.get("oracle_db")
    if not db:
        return
    freshness = FreshnessGovernor(application)
    rows = await db.fetchall("SELECT group_id FROM group_profile")
    for row in rows:
        group_id = int(row[0])
        recent = await db.fetchone("SELECT MAX(last_seen) FROM members WHERE group_id=?", (group_id,))
        if not recent or float(recent[0] or 0) < time.time() - 86400:
            continue
        previous = await db.fetchone("SELECT sent_at FROM scheduled_log WHERE group_id=? AND schedule_type LIKE 'pulse:%' ORDER BY sent_at DESC LIMIT 1", (group_id,))
        if previous and time.time() - float(previous[0]) < 6 * 3600:
            continue
        # Give both creative modes a chance; freshness decides whether the selected
        # piece is eligible for this group rather than repeating a recent experience.
        for _ in range(4):
            piece = generate_story() if random.random() < 0.52 else generate_gossip()
            if freshness.accept(group_id, piece.kind, piece.text):
                break
        else:
            continue
        try:
            await application.bot.send_message(group_id, piece.text, parse_mode="Markdown", disable_web_page_preview=True)
            await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)", (group_id, f"pulse:{piece.kind}", time.time()))
        except Exception:
            continue


def install(application) -> None:
    """Install exactly one 90-minute Pulse job."""
    if application.bot_data.get("_oracle_pulse_installed"):
        return
    if application.job_queue is None:
        raise RuntimeError("ORACLE_PULSE_REQUIRES_JOB_QUEUE")
    application.job_queue.run_repeating(pulse_callback, interval=90 * 60, first=90 * 60, name="oracle_pulse")
    application.bot_data["_oracle_pulse_installed"] = True
