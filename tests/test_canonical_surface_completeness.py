import os
import unittest


class CanonicalSurfaceCompletenessTests(unittest.TestCase):
    def test_canonical_runtime_keeps_core_and_preserved_surfaces(self):
        os.environ.setdefault("BOT_TOKEN", "test-token")
        from midnight_oracle.main import build_application

        app = build_application()
        commands = {
            str(command).lower().lstrip("/")
            for handlers in app.handlers.values()
            for handler in handlers
            for command in (getattr(handler, "commands", None) or ())
        }
        required = {
            "start", "help", "oracle", "truth", "memory", "house",
            "quiz", "riddle", "hangman", "tictactoe", "wordle",
            "hug", "kiss", "bestie", "ship", "bond",
            "daily", "balance", "gamble", "marry", "inventory",
            "deathgame", "survive", "roulette", "cricket",
            "oraclepair", "mprofile", "achievements", "cricketduel",
        }
        missing = sorted(required - commands)
        self.assertFalse(missing, f"canonical runtime dropped required commands: {missing}")

    def test_canonical_runtime_has_one_message_router(self):
        os.environ.setdefault("BOT_TOKEN", "test-token")
        from midnight_oracle.main import build_application

        app = build_application()
        message_callbacks = [
            getattr(handler, "callback", None)
            for handlers in app.handlers.values()
            for handler in handlers
            if handler.__class__.__name__ == "MessageHandler"
        ]
        self.assertTrue(any(getattr(callback, "__name__", "") == "_route_message" for callback in message_callbacks))


if __name__ == "__main__":
    unittest.main()
