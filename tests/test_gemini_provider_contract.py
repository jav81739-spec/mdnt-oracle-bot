from pathlib import Path

from midnight_oracle.voice_engine import VoiceEngine


ROOT = Path(__file__).resolve().parents[1]


def test_conversation_brain_uses_gemini_only():
    source = (ROOT / "midnight_oracle" / "generators" / "reply_generator.py").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in source
    assert "generateContent" in source
    assert "AsyncOpenAI" not in source


def test_voice_engine_uses_gemini_tts_and_telegram_compatible_audio():
    source = (ROOT / "midnight_oracle" / "voice_engine.py").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in source
    assert "gemini-3.1-flash-tts-preview" in source or "GEMINI_TTS_MODEL" in source
    assert "audio/ogg_opus" in source
    assert "AsyncOpenAI" not in source


def test_voice_requires_explicit_trigger():
    engine = VoiceEngine(api_key="test-key")
    decision = engine.decide(
        chat_id=1,
        user_id=2,
        text="I have a voice problem",
        direct=False,
        private=False,
        explicit=False,
    )
    assert decision.should_send is False
    assert decision.reason == "trigger_required"


def test_voice_explicit_request_is_allowed():
    engine = VoiceEngine(api_key="test-key")
    decision = engine.decide(
        chat_id=1,
        user_id=2,
        text="send me a voice note",
        direct=True,
        private=False,
        explicit=True,
    )
    assert decision.should_send is True
    assert decision.reason == "explicit_voice"
