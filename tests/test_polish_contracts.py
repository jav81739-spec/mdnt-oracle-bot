from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_transport_logs_do_not_run_at_info():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert 'logging.getLogger("httpx").setLevel(logging.WARNING)' in source
    assert 'logging.getLogger("httpcore").setLevel(logging.WARNING)' in source


def test_oracle_giphy_media_has_attribution():
    source = (ROOT / "core" / "oracle_pulse.py").read_text(encoding="utf-8")
    assert 'caption="Powered By GIPHY"' in source


def test_ai_has_live_model_discovery_fallback():
    source = (ROOT / "core" / "ai.py").read_text(encoding="utf-8")
    assert "_discover_model" in source
    assert "supportedGenerationMethods" in source
    assert 'DEFAULT_MODEL = "gemini-3.7-flash"' in source
