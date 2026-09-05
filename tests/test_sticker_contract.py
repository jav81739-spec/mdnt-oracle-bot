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


def test_legacy_configured_sticker_catalog_is_preserved():
    source = (ROOT / "handlers" / "chat.py").read_text(encoding="utf-8")
    assert source.count("CAACAgUAAxkBAAEG") == 10
    assert "CAACAgUAAxkBAAEGBzJqdp9ai3sYNonxPitgXwW1HsGYLQACigEAAqMYnj7IByAbmW8_0z0E" in source
    assert "CAACAgUAAxkBAAEGBzBqdp8mL5Juj0jyC3nh7q2mdBwJbAACyRMAAlJekFeBRat3I0udiz0E" in source
    assert "CAACAgUAAxkBAAEGBy5qdp8Uv6Pi3-VK9BJ7nn8_08Ju5wACsQQAAqQhMVYQIkv-OAABHc49BA" in source
    assert "CAACAgUAAxkBAAEGByxqdp7ystKCl2Rj7YKklllelMrR2gACqRUAAkggCFejMbHj9ySCNj0E" in source
    assert "CAACAgUAAxkBAAEGByZqdp6sg55QIGUcBVbW5ZvbvR1B8QACFhEAAlYTiVduxmgSyR8nUT0E" in source
    assert "CAACAgUAAxkBAAEGBxxqdp587c9-Vw1hftneSbQ9pWWtXQAC5BgAAremsVRaWlNEWRIuZz0E" in source
    assert "CAACAgUAAxkBAAEGBxpqdp5twHyvyAABbNEdbXdkTXCb7eAAAukaAAK32rhVVsDSda6ab2w9BA" in source
    assert "CAACAgUAAxkBAAEGBzRqdp_FeJQQ3EJfKq_Y7fZ-5l9lngAC5wEAAq4xRgWFtzPKdb1ZuD0E" in source
    assert "CAACAgUAAxkBAAEGBzZqdp_rySrqxo6FHWJ7J7VCq9HesAAC_xAAAn9jEVbXO-B4ukFDLz0E" in source
    assert "CAACAgUAAxkBAAEGBzhqdqAQk68E9J2t0sf1bwMizD3_ogACqgMAAnC-SFblo1QW5PoU0D0E" in source
