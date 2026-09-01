from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stickers_are_not_unsolicited():
    source = (ROOT / "midnight_oracle" / "handlers" / "sticker_handler.py").read_text(encoding="utf-8")
    assert "send sticker" in source
    assert "sticker bhejo" in source
    assert "ho gaya" not in source
    assert "tired" not in source


def test_ambient_sticker_rate_is_one_per_hour():
    source = (ROOT / "midnight_oracle" / "config.py").read_text(encoding="utf-8")
    assert "MAX_STICKER_EVENTS_PER_HOUR=1" in source
