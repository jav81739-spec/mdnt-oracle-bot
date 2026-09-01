from __future__ import annotations

import unittest

from midnight_oracle.friend_engine import FriendEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator
from midnight_oracle.handlers.sticker_handler import StickerHandler


class ConversationIntegrityTests(unittest.TestCase):
    def test_ambient_engine_rejects_plain_statement_without_social_opening(self):
        self.assertFalse(
            FriendEngine._ambient_opening(
                "I have a voice problem",
                "i have a voice problem",
                type("Context", (), {"recent_messages": []})(),
                type("Signal", (), {"social": 0.0})(),
            )
        )

    def test_ambient_engine_accepts_explicit_question(self):
        self.assertTrue(
            FriendEngine._ambient_opening(
                "what do you think?",
                "what do you think?",
                type("Context", (), {"recent_messages": []})(),
                type("Signal", (), {"social": 0.0})(),
            )
        )

    def test_gemini_3_request_has_no_legacy_sampling_or_prefilled_model_turns(self):
        generator = ReplyGenerator()
        payload = generator._request(
            "Room", "Member", "known", "hello", "neutral", "22", False, "none", ["Member: old", "Oracle: old reply"]
        )
        self.assertEqual([item["role"] for item in payload["contents"]], ["user"])
        self.assertNotIn("candidateCount", payload["generationConfig"])
        self.assertNotIn("temperature", payload["generationConfig"])
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "hello")

    def test_sticker_requires_a_clear_request(self):
        self.assertTrue(StickerHandler._REQUEST.fullmatch("send me a sticker"))
        self.assertTrue(StickerHandler._REQUEST.fullmatch("sticker please"))
        self.assertFalse(StickerHandler._REQUEST.fullmatch("I have a voice problem"))
        self.assertFalse(StickerHandler._REQUEST.fullmatch("send me a sticker for no reason and keep chatting"))
        self.assertIsNotNone(StickerHandler._NEGATIVE.search("don't send me a sticker"))


if __name__ == "__main__":
    unittest.main()
