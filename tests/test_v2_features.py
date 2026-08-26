from core.v2_features import CRICKET_SHOTS, _scorecard


def test_cricket_has_distinct_non_economy_shots():
    assert {"cover", "pull", "loft", "defend", "sweep", "reverse"}.issubset(CRICKET_SHOTS)
    assert all(len(value) == 4 for value in CRICKET_SHOTS.values())


def test_cricket_scorecard_contains_no_economy_fields():
    state = {
        "over": 1,
        "ball": 2,
        "runs": 9,
        "wickets": 1,
        "balls_left": 4,
        "target": 30,
        "commentary": "clean timing.",
    }
    card = _scorecard(state)
    assert "MIDNIGHT" in card
    assert "coins" not in card.lower()
    assert "wallet" not in card.lower()


def test_upgrade_alias_is_intentionally_supported():
    from core.v2_features import install
    assert callable(install)
