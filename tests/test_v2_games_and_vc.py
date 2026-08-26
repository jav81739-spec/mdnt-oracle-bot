from core.cricket_v2 import SHOTS
from core.vc_player import Track


def test_cricket_is_skill_first_and_has_multiple_shots():
    assert len(SHOTS) >= 6
    assert SHOTS["defend"][2] == 0
    assert SHOTS["reverse"][2] > SHOTS["cover"][2]


def test_track_serializes_cleanly():
    track = Track("Midnight Song", "https://example.test/audio", "https://example.test/watch", 123)
    assert track.as_dict()["title"] == "Midnight Song"
    assert track.as_dict()["duration"] == 123


def test_deathgames_v2_exposes_core_commands():
    from handlers import deathgames_v2
    for name in ("deathgame", "joingame", "startround", "kill", "vote", "endgame", "survive", "revive", "deathstatus", "roulette"):
        assert callable(getattr(deathgames_v2, name))
