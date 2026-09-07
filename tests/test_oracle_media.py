import unittest
from unittest.mock import AsyncMock, patch

from core import oracle_media


class OracleMediaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        oracle_media._last_sent.clear()
        oracle_media._recent_terms.clear()

    async def test_contextual_intent_uses_narrative_kind_and_real_chat_id(self):
        with patch.object(oracle_media.random, "random", return_value=0.0), patch.object(
            oracle_media.random, "choice", return_value="story reaction"
        ), patch.object(oracle_media, "_gif_lookup", return_value=AsyncMock(return_value="https://gif.test/story")) as lookup:
            media = await oracle_media.choose_media(
                "A serialized story about the group",
                kind="story",
                intent="contextual",
                chat_id=12345,
            )

        self.assertEqual(media["kind"], "gif")
        self.assertEqual(media["term"], "story reaction")
        lookup.return_value.assert_awaited_once_with("story reaction")
        self.assertIn("12345", oracle_media._recent_terms)

    async def test_gif_send_marks_chat_cooldown_only_after_success(self):
        bot = type("Bot", (), {"send_animation": AsyncMock()})()
        ok = await oracle_media.send_additive_gif(bot, 12345, "https://gif.test/x")
        self.assertTrue(ok)
        bot.send_animation.assert_awaited_once_with(
            chat_id=12345, animation="https://gif.test/x", reply_to_message_id=None
        )
        self.assertFalse(oracle_media._eligible("12345"))

    async def test_gif_send_failure_does_not_consume_cooldown(self):
        bot = type("Bot", (), {"send_animation": AsyncMock(side_effect=RuntimeError("provider"))})()
        ok = await oracle_media.send_additive_gif(bot, 12345, "https://gif.test/x")
        self.assertFalse(ok)
        self.assertTrue(oracle_media._eligible("12345"))


if __name__ == "__main__":
    unittest.main()
