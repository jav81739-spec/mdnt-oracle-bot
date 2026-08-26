from core.v2_social2 import ACTIONS, ALIASES, relevant_comment


def test_v2_has_large_original_interaction_surface():
    assert len(ACTIONS) >= 20
    for command in ("hug", "kiss", "pat", "kick", "highfive", "cuddle", "poke", "bonk", "cheer", "comfort"):
        assert command in ALIASES


def test_channel_comment_is_cricket_relevant():
    comment = relevant_comment("India win a T20 match by 8 wickets with 190 runs")
    assert any(word in comment.lower() for word in ("cricket", "boundary", "update", "timeline", "scene"))


def test_channel_comment_handles_generic_post():
    comment = relevant_comment("new edit is out tonight")
    assert comment
