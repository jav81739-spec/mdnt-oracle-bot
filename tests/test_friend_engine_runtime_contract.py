from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_friend_engine_does_not_schedule_a_second_cold_start_bootstrap():
    source = (ROOT / "handlers" / "friend_engine.py").read_text(encoding="utf-8")
    assert "canonical_surface_startup" not in source
    assert "run_once(_canonical_startup" not in source
    assert "run_daily(morning" in source
    assert "run_daily(evening" in source
    assert "run_daily(night" in source
