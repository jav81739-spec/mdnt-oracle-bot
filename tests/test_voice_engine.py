from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from midnight_oracle.voice_engine import VOICE_PROFILE, VoiceEngine


class VoiceEngineTests(unittest.IsolatedAsyncioTestCase):
    def test_without_api_key_voice_is_disabled(self):
        engine = VoiceEngine(api_key="")
        decision = engine.decide(chat_id=1, user_id=2, text="hello", direct=True, private=True)
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "voice_unconfigured")

    def test_ordinary_voice_word_requires_trigger(self):
        engine = VoiceEngine(api_key="test-key")
        decision = engine.decide(
            chat_id=1, user_id=2, text="I have a voice problem", direct=False, private=False, explicit=False
        )
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "trigger_required")

    def test_long_script_is_bounded(self):
        text = "x" * 1000
        self.assertEqual(len(VoiceEngine._clean_script(text)), 700)

    async def test_synthesis_uses_gemini_and_telegram_ogg_opus(self):
        engine = VoiceEngine(api_key="test-key")
        response = AsyncMock()
        response.status_code = 200
        response.json.return_value = {"output_audio": {"data": "YXVkaW8="}}

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post.return_value = response

        with patch("midnight_oracle.voice_engine.httpx.AsyncClient", return_value=client):
            with patch("midnight_oracle.voice_engine.random.choice", return_value="natural delivery"):
                audio = await engine.synthesize("hello")

        self.assertIsNotNone(audio)
        self.assertEqual(audio.name, "midnight-oracle.ogg")
        self.assertEqual(audio.read(), b"audio")
        client.post.assert_awaited_once()
        payload = client.post.await_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemini-3.1-flash-tts-preview")
        self.assertEqual(payload["response_format"]["mime_type"], "audio/ogg_opus")
        self.assertEqual(payload["generation_config"]["speech_config"][0]["voice"], VOICE_PROFILE["voice"])

    def test_explicit_request_is_deterministic(self):
        engine = VoiceEngine(api_key="test-key")
        decision = engine.decide(
            chat_id=1,
            user_id=2,
            text="send me a voice",
            direct=True,
            private=False,
            explicit=True,
        )
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "explicit_voice")

    def test_explicit_request_has_short_cooldown_after_recording(self):
        engine = VoiceEngine(api_key="test-key")
        engine.record(1, 2, "first voice")
        decision = engine.decide(
            chat_id=1,
            user_id=2,
            text="send me another voice",
            direct=True,
            private=False,
            explicit=True,
        )
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "explicit_cooldown")

    def test_duplicate_is_rejected_after_cooldown_is_cleared(self):
        engine = VoiceEngine(api_key="test-key")
        first = engine.decide(
            chat_id=1,
            user_id=2,
            text="send me a voice note",
            direct=True,
            private=False,
            explicit=True,
        )
        self.assertTrue(first.should_send)
        engine.record(1, 2, "send me a voice note")
        engine._last_chat[1] = 0
        second = engine.decide(
            chat_id=1,
            user_id=2,
            text="send me a voice note",
            direct=True,
            private=False,
            explicit=True,
        )
        self.assertFalse(second.should_send)
        self.assertEqual(second.reason, "duplicate")


if __name__ == "__main__":
    unittest.main()
