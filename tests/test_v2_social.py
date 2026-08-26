from core.v2_social2 import ACTIONS, ALIASES, relevant_comment


def test_v2_has_large_original_interaction_surface():
    assert len(ACTIONS) >= 20
    for command in ("hug", "kiss", "pat", "kick", "highfive", "cuddle", "poke", "bonk", "cheer", "comfort"):
        assert command in ALIASES


def test_channel_comment_is_cricket_relevant():
    comment = relevant_comment("India win a T20 match by 8 wickets with 190 runs")
    assert any(word in comment.lower() for word in ("cricket", "boundary", "update", "scene", "result"))


def test_channel_comment_is_edit_relevant():
    comment = relevant_comment("new cricket edit video is out tonight")
    assert any(word in comment.lower() for word in ("edit", "visual", "video"))


def test_channel_comment_handles_media_only_post():
    comment = relevant_comment("")
    assert comment
    assert any(word in comment.lower() for word in ("visual", "caption", "frame", "seen"))


def test_channel_comment_is_not_a_generic_fixed_fallback():
    cricket = relevant_comment("wicket and innings update")
    edit = relevant_comment("new montage edit")
    assert cricket != edit
