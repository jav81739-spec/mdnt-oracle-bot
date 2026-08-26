import unittest


class GamePersistenceBoundaryTests(unittest.TestCase):
    def test_stateful_game_handlers_are_wrapped(self):
        from handlers import games

        expected = {
            "riddle", "riddle_answer", "scramble", "unscramble",
            "hangman", "hangman_guess", "tictactoe", "ttt_move",
            "wordchain_start", "chain_word", "wordle", "wordle_guess",
            "rock_paper_scissors", "guess_number", "leaderboard_cmd",
        }
        for name in expected:
            fn = getattr(games, name)
            self.assertIsNotNone(getattr(fn, "__wrapped__", None), name)

    def test_game_state_encodes_sets_and_numeric_user_ids(self):
        from core.game_runtime import _decode, _encode

        value = {"12": {"guessed": {"a", "b"}}, "turn": 12}
        encoded = _encode(value)
        decoded = _decode(encoded)
        self.assertEqual(decoded[12]["guessed"], {"a", "b"})
        self.assertEqual(decoded["turn"], 12)


if __name__ == "__main__":
    unittest.main()
