"""Unit tests for the dependency-free FriendEngine."""
from __future__ import annotations

from friend_engine import FriendEngine


def _ctx(**overrides):
    """Build a deterministic FriendEngine test context."""
    context = {
        "sender": "u1",
        "group_id": "g1",
        "recent_messages": [],
        "hour": 14,
        "is_late_night": False,
        "now": 1000.0,
        "social_cooldown_seconds": 0,
        "ambient_engagement_rate": 1.0,
    }
    context.update(overrides)
    return context


def test_tiredness_detection():
    """Tiredness should cross the social threshold and produce a reply."""
    ok, reply = FriendEngine(seed=1).should_engage("yaar aaj bahut thak gaya", _ctx())
    assert ok and reply


def test_celebration_detection():
    """Celebration language should produce a celebratory reply."""
    ok, reply = FriendEngine(seed=1).should_engage("finally ho gaya bhai 😭", _ctx())
    assert ok and reply


def test_cooldown_blocking():
    """A group cooldown must block the next ambient reply."""
    engine = FriendEngine(seed=1)
    ctx = _ctx(now=1000.0)
    assert engine.should_engage("yaar aaj bahut thak gaya", ctx)[0]
    assert not engine.should_engage("yaar kya scene hai", _ctx(now=1001.0))[0]


def test_late_night_tone():
    """Late-night replies should carry the quieter Oracle tone."""
    ok, reply = FriendEngine(seed=1).should_engage(
        "yaar aaj bahut thak gaya", _ctx(is_late_night=True)
    )
    assert ok and "🌙" in reply


def test_hinglish_input():
    """Hinglish emotional language should be recognized without translation."""
    ok, reply = FriendEngine(seed=1).should_engage("neend aa rahi hai yaar", _ctx())
    assert ok and reply


def test_direct_summon_bypass_is_not_engine_behavior():
    """Direct summons are intentionally outside FriendEngine and must not be consumed by it."""
    ok, reply = FriendEngine(seed=1).should_engage("@midnight help me", _ctx())
    assert not ok and reply is None


def test_score_threshold_rejection():
    """A neutral informational message should remain silent."""
    ok, reply = FriendEngine(seed=1).should_engage("the meeting is at six", _ctx())
    assert not ok and reply is None


def test_max_hourly_reply_cap():
    """No more than two ambient replies may be produced in one hour per group."""
    engine = FriendEngine(seed=1)
    assert engine.should_engage("yaar aaj bahut thak gaya", _ctx(sender="u1", now=1000))[0]
    assert engine.should_engage("finally ho gaya bhai", _ctx(sender="u2", now=2000))[0]
    assert not engine.should_engage("kya bakwas yaar", _ctx(sender="u3", now=2500))[0]
