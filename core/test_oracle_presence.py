from core.oracle_presence import decide_presence


def test_quiet_room_stays_silent():
    decision = decide_presence(group_id=1, now=1000, active_count=1, context_items=[], last_delivery=None, cooldown_seconds=10800)
    assert decision.speak is False
    assert decision.strategy == "silence"


def test_recent_context_can_create_an_opportunity():
    decision = decide_presence(
        group_id=1,
        now=1000,
        active_count=5,
        context_items=[{"text": f"topic {i}", "ts": 1000} for i in range(4)],
        last_delivery=None,
        cooldown_seconds=10800,
    )
    assert decision.score > 0.56
    assert decision.strategy in {"story", "curiosity", "playful_observation", "gossip"}


def test_cooldown_always_wins():
    decision = decide_presence(
        group_id=1,
        now=1000,
        active_count=10,
        context_items=[{"text": "busy room", "ts": 1000}],
        last_delivery=999,
        cooldown_seconds=10800,
    )
    assert decision.speak is False
    assert decision.reason == "cooldown"
