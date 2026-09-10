"""Oracle Pulse: canonical decision-to-delivery presence pipeline."""
from __future__ import annotations
import time
from .oracle_delivery import deliver
from .oracle_freshness import FreshnessGovernor
from .oracle_mind import generate_contextual_piece,language_hint
from .oracle_narrative import maybe_deliver as maybe_deliver_narrative,rollback as rollback_narrative
from .oracle_presence import decide_presence
from .oracle_strategy import build_strategy
from midnight_oracle.utils.logger import get_logger
log=get_logger("midnight.oracle_pulse")
CHECK_INTERVAL=15*60; DELIVERY_COOLDOWN=3*3600; ACTIVE_WINDOW=6*3600

async def _deliver_narrative(application,group_id,text):
    """Deliver Oracle Pulse as text only; visuals are never appended automatically."""
    return await deliver(application,group_id,text)

async def pulse_callback(context):
    application=context.application;db=application.bot_data.get("oracle_db")
    if not db:return
    freshness=FreshnessGovernor(application);atmosphere=application.bot_data.get("oracle_atmosphere",{})
    try:
        from startup import get_chat_registry
        registry=await get_chat_registry();targets=[int(cid) for cid,info in registry.items() if info.get("type") in ("group","supergroup")]
    except Exception:targets=[]
    if not targets:return
    now=time.time()
    for group_id in targets:
        try:
            if await db.cooldown_active("group",str(group_id),"delivery_blocked",now):
                try:
                    member=await application.bot.get_chat_member(group_id,application.bot.id)
                    if getattr(member,"can_send_messages",None) is False:continue
                    await db.execute("DELETE FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?",("group",str(group_id),"delivery_blocked"))
                except Exception:continue
            active=await db.fetchall("SELECT user_id FROM members WHERE group_id=? AND last_seen>? LIMIT 12",(group_id,now-ACTIVE_WINDOW));items=list(atmosphere.get(str(group_id),[]))[-8:]
            previous=await db.fetchone("SELECT sent_at FROM scheduled_log WHERE group_id=? AND schedule_type LIKE 'pulse:%' ORDER BY sent_at DESC LIMIT 1",(group_id,));last_delivery=float(previous[0]) if previous else None
            decision=decide_presence(group_id=group_id,now=now,active_count=len(active),context_items=items,last_delivery=last_delivery,cooldown_seconds=DELIVERY_COOLDOWN);contract=build_strategy(decision,language_hint(items))
            if not decision.speak:continue
            narrative_text,narrative_state,narrative_kind,narrative_id,previous_part=await maybe_deliver_narrative(db,application,group_id,contract.strategy,items,now)
            if narrative_text is not None:
                accepted_kind=narrative_kind or "story"
                if not freshness.accept(group_id,accepted_kind,narrative_text,theme=f"serialized:{narrative_state}",media=None,pair=contract.target_policy,strategy="serialized_narrative"):
                    if narrative_id is not None and previous_part is not None:await rollback_narrative(db,narrative_id,previous_part,now)
                    continue
                if await _deliver_narrative(application,group_id,narrative_text):
                    await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)",(group_id,f"pulse:{accepted_kind}",now))
                continue
            accepted=None
            for attempt in range(6):
                piece=await generate_contextual_piece(items,seed=f"{group_id}:{int(now//CHECK_INTERVAL)}:{contract.strategy}:{attempt}",strategy=contract.strategy)
                if freshness.accept(group_id,piece.kind,piece.text,theme=contract.reason,media=None,pair=contract.target_policy,strategy=contract.strategy):accepted=piece;break
            if accepted is None:continue
            if await _deliver_narrative(application,group_id,accepted.text):await db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)",(group_id,f"pulse:{accepted.kind}",now))
        except Exception:log.exception("ORACLE_PULSE_STAGE | stage=runtime_error | chat=%s",group_id)

def install(application):application.bot_data["_oracle_pulse_installed"]=True
