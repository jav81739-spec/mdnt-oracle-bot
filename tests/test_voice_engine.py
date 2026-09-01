from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from midnight_oracle.voice_engine import VoiceEngine


class VoiceEngineTests(unittest.IsolatedAsyncioTestCase):
    def test_without_api_key_voice_is_disabled(self):
        engine = VoiceEngine(api_key="")
        decision = engine.decide(chat_id=1, user_id=2, text="hello", direct=True, private=True)
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "voice_unconfigured")

    def test_long_script_is_bounded(self):
        text = "x" * 1000
        self.assertEqual(len(VoiceEngine._clean_script(text)), 700)

    async def test_synthesis_uses_opus_and_returns_named_buffer(self):
        engine = VoiceEngine(api_key="test-key")
        response = type("Response", (), {"content": b"audio"})()
        engine.client.audio.speech.create = AsyncMock(return_value=response)
        audio = await engine.synthesize("hello")
        self.assertIsNotNone(audio)
        self.assertEqual(audio.name, "midnight-oracle.ogg")
        self.assertEqual(audio.read(), b"audio")
        engine.client.audio.speech.create.assert_awaited_once_with(
            model="gpt-4o-mini-tts", voice="alloy", input="hello", response_format="opus"
        )

    def test_duplicate_is_rejected_after_recording(self):
        engine = VoiceEngine(api_key="test-key")
        with patch("midnight_oracle.voice_engine.random.random", return_value=0.0):
            first = engine.decide(chat_id=1, user_id=2, text="say this", direct=True, private=False)
        self.assertTrue(first.should_send)
        engine.record(1, 2, "say this")
        second = engine.decide(chat_id=1, user_id=2, text="say this", direct=True, private=False)
        self.assertFalse(second.should_send)
        self.assertEqual(second.reason, "chat_cooldown")


if __name__ == "__main__":
    unittest.main()
