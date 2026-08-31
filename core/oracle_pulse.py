"""Oracle Pulse: canonical decision-to-delivery presence pipeline."""
from __future__ import annotations

import time

from .oracle_delivery import deliver
from .oracle_freshness import FreshnessGovernor
from .oracle_mind import generate_contextual_piece, language_hint
from .oracle_presence import decide_presence
from .oracle_strategy import build_strategy
from midnight_oracle.utils.logger import get_logger

log = get_logger("midnight.oracle_pulse")
CHECK_INTERVAL = 15 * 60
DELIVERY_COOLDOWN = 3 * 3600
ACTIVE_WINDOW = 6 * 3600


def _log(message: str, *args) -> None:
    """Emit compact stage markers without exposing message/member content."""
    log.info(message, *args)


async def pulse_callback(context) -> None:
    """Run Presence → Strategy → Mind → Freshness → Social delivery."""
    application = context.application
    db = application.bot_data.get("oracle_db")
    if not db:
        _log("ORACLE_PULSE_STOP | stage=db")
        return

    freshness = FreshnessGovernor(application)
    atmosphere = application.bot_data.get("oracle_atmosphere", {})
    try:
        from startup import get_chat_registry
        registry = await get_chat_registry()
        targets = [int(cid) for cid, info in registry.items() if info.get("type") in ("group", "supergroup")]
    except Exception:
        targets = []

    if not targets:
        _log("ORACLE_PULSE_STOP | stage=registry | targets=0")
        return

    now = time.time()
    _log("ORACLE_PULSE_STAGE | stage=registry | targets=%d", len(targets))

    for group_id in targets:
        try:
            blocked = await db.cooldown_active("group", str(group_id), "delivery_blocked", now)
            if blocked:
                try:
                    member = await application.bot.get_chat_member(group_id, application.bot.id)
                    can_send = getattr(member, "can_send_messages", None)
                    if can_send is False:
                        _log("ORACLE_PULSE_SKIP | stage=delivery | chat=%s | reason=permission_blocked", group_id)
                        continue
                    await db.execute(
                        "DELETE FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?",
                        ("group", str(group_id), "delivery_blocked"),
                    )
                    _log("ORACLE_PULSE_RECOVERED | stage=delivery | chat=%s | reason=permission_restored", group_id)
                except Exception:
                    _log("ORACLE_PULSE_SKIP | stage=delivery | chat=%s | reason=permission_check_failed", group_id)
                    continue

            active = await db.fetchall(
                "SELECT user_id FROM members WHERE group_id=? AND last_seen>? LIMIT 12",
                (group_id, now - ACTIVE_WINDOW),
            )
            items = list(atmosphere.get(str(group_id), []))[-8:]
            _log("ORACLE_PULSE_STAGE | stage=eligibility | chat=%s | active=%d | context=%d", group_id, len(active), len(items))

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
            contract = build_strategy(decision, language_hint(items))
            _log(
                "ORACLE_PULSE_STAGE | stage=decision | chat=%s | speak=%s | strategy=%s | interaction=%s",
                group_id, decision.speak, contract.strategy, contract.interaction,
            )
            if not decision.speak:
                continue

            accepted = None
            for attempt in range(6):
                piece = await generate_contextual_piece(
                    items,
                    seed=f"{group_id}:{int(now // CHECK_INTERVAL)}:{contract.strategy}:{attempt}",
                    strategy=contract.strategy,
                )
                if freshness.accept(
                    group_id,
                    piece.kind,
                    piece.text,
                    theme=contract.reason,
                    media=contract.media_intent,
                    pair=contract.target_policy,
                    strategy=contract.strategy,
                ):
                    accepted = piece
                    break
            if accepted is None:
                _log("ORACLE_PULSE_STAGE | stage=generation | chat=%s | accepted=false", group_id)
                continue

            _log("ORACLE_PULSE_STAGE | stage=generation | chat=%s | accepted=true | kind=%s", group_id, accepted.kind)
            delivered = await deliver(application, group_id, accepted.text)
            if not delivered:
                _log("ORACLE_PULSE_STAGE | stage=delivery | chat=%s | delivered=false", group_id)
                continue
            await db.execute(
                "INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)",
                (group_id, f"pulse:{accepted.kind}", now),
            )
            _log("ORACLE_PULSE_STAGE | stage=delivery | chat=%s | delivered=true", group_id)
        except Exception:
            log.exception("ORACLE_PULSE_STAGE | stage=runtime_error | chat=%s", group_id)
            continue


def install(application) -> None:
    """Compatibility hook; the canonical scheduler owns Pulse registration."""
    application.bot_data["_oracle_pulse_installed"] = True
