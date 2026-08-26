"""Restart recovery for persistent, one-shot Midnight jobs."""
from __future__ import annotations

import logging

from .storage import Storage, storage

log = logging.getLogger("midnight.recovery")


async def recover_deathgames(application, legacy_module, store: Storage = storage) -> int:
    """Recover death-game collection timers after a Render/process restart.

    The original game stores ``dg_active:<chat_id>`` with a 24-hour TTL while
    players are being collected. Its 5-minute JobQueue timer is process-local,
    so it disappears on restart. Redis TTL gives us enough durable timing data
    to reconstruct that one-shot job without changing the live command flow.

    A game already marked ``running`` cannot be safely reconstructed because
    the old round loop kept its current alive-player list only in memory. We
    therefore fail closed: mark it interrupted and refund the 100-coin stake
    for each recorded player rather than silently losing balances or inventing
    a winner.
    """
    recovered = 0
    keys = await store.scan("dg_active:*")
    for key in keys:
        try:
            chat_id = int(key.split(":", 1)[1])
        except (IndexError, ValueError):
            continue

        status = await store.get(key, "")
        if status == "collecting":
            ttl = await store.ttl(key)
            if ttl < 0:
                continue
            elapsed = max(0, 86400 - ttl)
            delay = max(0, 300 - elapsed)
            name = f"dg_recovery_{chat_id}"
            if application.job_queue.get_jobs_by_name(name):
                continue
            application.job_queue.run_once(
                legacy_module._start_death_rounds,
                delay,
                data={"chat_id": chat_id},
                name=name,
                chat_id=chat_id,
            )
            recovered += 1
            continue

        if status == "running":
            # The old round state is not durable. Refund the recorded stakes
            # and clear the abandoned game rather than creating a phantom win.
            raw = await store.get(f"dg_players:{chat_id}", "[]")
            try:
                players = __import__("json").loads(raw or "[]")
            except Exception:
                players = []
            for player in players:
                try:
                    uid = int(player["uid"])
                    await legacy_module._addcoins(uid, 100)
                except Exception:
                    log.exception("Failed refund during death-game recovery chat=%s", chat_id)
            await store.delete(key, f"dg_players:{chat_id}")
            try:
                await application.bot.send_message(
                    chat_id,
                    "🌑 Midnight restarted while a Death Game was running. "
                    "The game was safely cancelled and recorded entry stakes were refunded.",
                )
            except Exception:
                log.info("Could not announce death-game recovery for chat=%s", chat_id)

    return recovered
