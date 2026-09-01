"""Import-level regression tests for the production command surface."""
from __future__ import annotations

import os
import unittest


class RuntimeSmokeTests(unittest.TestCase):
    def test_all_handler_modules_import(self):
        import handlers.aesthetic
        import handlers.chat
        import handlers.deathgames
        import handlers.deathgames_v2
        import handlers.economy
        import handlers.events
        import handlers.friendship
        import handlers.fun
        import handlers.games
        import handlers.marriage
        import handlers.matchmaking
        import handlers.mentions
        import handlers.moderation
        import handlers.stats
        import handlers.storage
        import handlers.timecapsule

    def test_chat_compatibility_surface(self):
        import handlers.chat as chat
        for name in ("generate_reply", "send_text_with_gif", "send_mood_gif", "get_gif_url", "send_random_gif", "send_random_sticker", "gif_reply", "sticker_reply", "maybe_react_to_message"):
            self.assertTrue(callable(getattr(chat, name)))

    def test_production_entrypoint_activates_v2_engine(self):
        os.environ.setdefault("BOT_TOKEN", "123456789:ci-test-token")
        import bot
        import handlers.deathgames_v2 as v2
        # The V2 binding is part of production application construction, not
        # import-time side effects. Build the application before asserting the
        # live compatibility surface.
        app = bot.build_application()
        self.assertIs(bot.legacy_bot.deathgames, v2)
        for name in ("survive", "revive", "deathstatus", "roulette", "deathgame", "joingame", "startround", "kill", "vote", "endgame"):
            self.assertTrue(callable(getattr(v2, name)))
        app.handlers.clear()

    def test_no_gemini_sdk_dependency_is_required(self):
        import pathlib
        requirements = pathlib.Path("requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("google-generativeai", requirements)


if __name__ == "__main__":
    unittest.main()
