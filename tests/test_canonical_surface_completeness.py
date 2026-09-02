import importlib
import os
import unittest


def _build_application_for_test():
    os.environ["BOT_TOKEN"] = "ci-test-token-1234567890"
    config = importlib.import_module("midnight_oracle.config")
    config.BOT_TOKEN = os.environ["BOT_TOKEN"]
    main = importlib.import_module("midnight_oracle.main")
    main.BOT_TOKEN = config.BOT_TOKEN
    return main.build_application()


class CanonicalSurfaceCompletenessTests(unittest.TestCase):
    def test_canonical_runtime_keeps_core_and_preserved_surfaces(self):
        app = _build_application_for_test()
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

    def test_canonical_runtime_has_one_primary_message_router(self):
        app = _build_application_for_test()
        callbacks = [
            getattr(handler, "callback", None)
            for handlers in app.handlers.values()
            for handler in handlers
            if handler.__class__.__name__ == "MessageHandler"
        ]
        self.assertTrue(any(getattr(callback, "__name__", "") == "_route_message" for callback in callbacks))


if __name__ == "__main__":
    unittest.main()
