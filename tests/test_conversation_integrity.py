from __future__ import annotations

import asyncio
import unittest

from midnight_oracle.friend_engine import FriendEngine
from midnight_oracle.generators.reply_generator import ReplyGenerator
from midnight_oracle.handlers.sticker_handler import StickerHandler


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content="hello back"):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response()


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class _Client:
    def __init__(self):
        self.chat = _Chat()


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

    def test_openai_request_uses_single_system_prompt_and_recent_context(self):
        client = _Client()
        generator = ReplyGenerator(client=client)
        result = asyncio.run(
            generator.generate(
                "Room", "Member", "known", "hello", "neutral", "22:00", False,
                "none", ["Member: old", "Oracle: old reply"]
            )
        )
        self.assertEqual(result, "hello back")
        payload = client.chat.completions.calls[0]
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Member: old", payload["messages"][0]["content"])
        self.assertEqual(payload["max_tokens"], 180)
        self.assertEqual(payload["temperature"], .86)

    def test_sticker_requires_a_clear_request(self):
        self.assertTrue(StickerHandler._REQUEST.fullmatch("send me a sticker"))
        self.assertTrue(StickerHandler._REQUEST.fullmatch("sticker please"))
        self.assertFalse(StickerHandler._REQUEST.fullmatch("I have a voice problem"))
        self.assertFalse(StickerHandler._REQUEST.fullmatch("send me a sticker for no reason and keep chatting"))
        self.assertIsNotNone(StickerHandler._NEGATIVE.search("don't send me a sticker"))


if __name__ == "__main__":
    unittest.main()
