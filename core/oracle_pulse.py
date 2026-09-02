"""Oracle Pulse: conservative autonomous presence pipeline."""
from __future__ import annotations

import re
import time

from .oracle_delivery import deliver
from .oracle_freshness import FreshnessGovernor
from .oracle_media import MEDIA_COOLDOWN, build_original_gif, choose_media
from .oracle_mind import generate_contextual_piece, language_hint
from .oracle_narrative import maybe_deliver as maybe_deliver_narrative, rollback as rollback_narrative
from .oracle_presence import decide_presence
from .oracle_strategy import build_strategy
from midnight_oracle.utils.logger import get_logger

log = get_logger("midnight.oracle_pulse")
CHECK_INTERVAL = 15 * 60
DELIVERY_COOLDOWN = 6 * 3600
ACTIVE_WINDOW = 6 * 3600
MEDIA_COOLDOWN_TYPE = "oracle_media"


def _log(message: str, *args) -> None:
    log.info(message, *args)


def _part_index(state: str | None) -> int | None:
    match = re.search(r"(?:part|p)[-_ ]?(\d+)", str(state or "").casefold())
    return int(match.group(1)) if match else None


async def _deliver_narrative_with_media(application, db, group_id: int, text: str, kind: str, state: str | None, now: float) -> bool:
    """Text is primary; one original contextual GIF/image may accompany it."""
    if not await deliver(application, group_id, text):
        return False
    if await db.cooldown_active("group", str(group_id), MEDIA_COOLDOWN_TYPE, now):
        return True
    try:
        part_index = _part_index(state)
        media = await choose_media(text, kind, part_index)
        if not media:
            return True
        if media["kind"] == "gif":
            if media.get("source") == "original":
                animation = build_original_gif(media.get("text", text), kind, media.get("part_index", part_index))
                await application.bot.send_animation(group_id, animation)
            else:
                await application.bot.send_animation(group_id, media["url"], caption="Powered By GIPHY")
        elif media["kind"] == "image":
            await application.bot.send_photo(group_id, media["url"])
        else:
            return True
        await db.set_cooldown("group", str(group_id), MEDIA_COOLDOWN_TYPE, now + MEDIA_COOLDOWN)
        _log("ORACLE_PULSE_STAGE | stage=media | chat=%s | kind=%s | source=%s | delivered=true", group_id, media["kind"], media.get("source", "provider"))
    except Exception:
        _log("ORACLE_PULSE_STAGE | stage=media | chat=%s | delivered=false", group_id)
    return True


async def pulse_callback(context) -> None:
    """Run Presence → Strategy → Mind → Freshness → Narrative/Media delivery."""
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
    for group_id in targets:
        try:
            blocked = await db.cooldown_active("group", str(group_id), "delivery_blocked", now)
            if blocked:
                try:
                    member = await application.bot.get_chat_member(group_id, application.bot.id)
                    if getattr(member, "can_send_messages", None) is False:
                        continue
                    await db.execute("DELETE FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?", ("group", str(group_id), "delivery_blocked"))
                except Exception:
                    continue

            active = await db.fetchall("SELECT user_id FROM members WHERE group_id=? AND last_seen>? LIMIT 12", (group_id, now - ACTIVE_WINDOW))
            items = list(atmosphere.get(str(group_id), []))[-8:]
            previous = await db.fetchone("SELECT sent_at FROM scheduled_log WHERE group_id=? AND schedule_type LIKE 'pulse:%' ORDER BY sent_at DESC LIMIT 1", (group_id,))
            last_delivery = float(previous[0]) if previous else None
            decision = decide_presence(group_id=group_id, now=now, active_count=len(active), context_items=items, last_delivery=last_delivery, cooldown_seconds=DELIVERY_COOLDOWN)
            if not decision.speak:
                continue
            contract = build_strategy(decision, language_hint(items))

            narrative_text, narrative_state, narrative_kind, narrative_id, previous_part = await maybe_deliver_narrative(db, application, group_id, contract.strategy, items, now)
            if narrative_text is not None:
                accepted_kind = narrative_kind or "story"
                if not FreshnessGovernor(application).accept(group_id, accepted_kind, narrative_text, theme=f"serialized:{narrative_state}", media=False, pair=contract.target_policy, strategy="serialized_narrative"):
                    if narrative_id is not None and previous_part is not None:
                        await rollback_narrative(db, narrative_id, previous_part, now)
                    continue
                current_part = previous_part + 1 if previous_part is not None else None
                delivered = await _deliver_narrative_with_media(application, db, group_id, narrative_text, accepted_kind, f"part:{current_part}" if current_part else narrative_state, now)
                if not delivered:
                    if narrative_id is not None and previous_part is not None:
                        await rollback_narrative(db, narrative_id, previous_part, now)
                    continue
                await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)", (group_id, f"pulse:{accepted_kind}", now))
                continue

            accepted = None
            for attempt in range(6):
                piece = await generate_contextual_piece(items, seed=f"{group_id}:{int(now // CHECK_INTERVAL)}:{contract.strategy}:{attempt}", strategy=contract.strategy)
                if freshness.accept(group_id, piece.kind, piece.text, theme=contract.reason, media=False, pair=contract.target_policy, strategy=contract.strategy):
                    accepted = piece
                    break
            if accepted is None:
                continue
            if not await _deliver_narrative_with_media(application, db, group_id, accepted.text, accepted.kind, None, now):
                continue
            await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)", (group_id, f"pulse:{accepted.kind}", now))
        except Exception:
            log.exception("ORACLE_PULSE_STAGE | stage=runtime_error | chat=%s", group_id)
            continue


def install(application) -> None:
    application.bot_data["_oracle_pulse_installed"] = True
