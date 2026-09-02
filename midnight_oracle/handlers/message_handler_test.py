"""Focused regression tests for Oracle continuation replies and original media."""
from __future__ import annotations

import io
import unittest
from types import SimpleNamespace

from .message_handler import _is_continuation_request, _reply_context
from core.oracle_media import build_original_gif


class MessageHandlerRegressionTests(unittest.TestCase):
    """Keep the exact Telegram failure mode from returning silently."""

    def test_more_is_a_continuation(self):
        self.assertTrue(_is_continuation_request("More"))
        self.assertTrue(_is_continuation_request("tell me more"))
        self.assertTrue(_is_continuation_request("aur batao"))
        self.assertFalse(_is_continuation_request("more about cricket"))

    def test_nested_oracle_story_is_recovered_from_gif_reply(self):
        bot_id = 777
        story = SimpleNamespace(
            from_user=SimpleNamespace(id=bot_id),
            text="The room went quiet when the second clue appeared.",
            caption=None,
            reply_to_message=None,
        )
        gif = SimpleNamespace(
            from_user=SimpleNamespace(id=bot_id),
            text=None,
            caption=None,
            animation=object(),
            photo=None,
            reply_to_message=story,
        )
        member_message = SimpleNamespace(reply_to_message=gif)
        context = _reply_context(member_message, bot_id)
        self.assertEqual(len(context), 2)
        self.assertIn("visual companion", context[0])
        self.assertIn("second clue appeared", context[1])

    def test_original_reaction_gif_is_real_gif_bytes(self):
        stream = build_original_gif("funny unexpected gossip", "gossip")
        self.assertIsInstance(stream, io.BytesIO)
        self.assertEqual(stream.read(6), b"GIF89a")


if __name__ == "__main__":
    unittest.main()
