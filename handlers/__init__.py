"""Handler package bootstrap.

The games module predates the durable core and keeps mutable state at module
scope. Wrap its stateful commands at package load so the existing command
surface is preserved while state becomes restart-safe and serialized.
"""
from . import games
from core.game_runtime import persistent_game_state


def _wrap(name: str, *state: str, key: str) -> None:
    setattr(games, name, persistent_game_state(*state, state_key=key)(getattr(games, name)))


# Shared state keys are intentional: start and answer/move commands must see
# the same durable record. Each record is still scoped to its Telegram chat.
_wrap("riddle", "active_riddles", key="riddle")
_wrap("riddle_answer", "active_riddles", key="riddle")
_wrap("scramble", "active_scrambles", key="scramble")
_wrap("unscramble", "active_scrambles", key="scramble")
_wrap("hangman", "active_hangman", key="hangman")
_wrap("hangman_guess", "active_hangman", key="hangman")
_wrap("tictactoe", "active_ttt", key="tictactoe")
_wrap("ttt_move", "active_ttt", key="tictactoe")
_wrap("wordchain_start", "active_wordchain", key="wordchain")
_wrap("chain_word", "active_wordchain", key="wordchain")
_wrap("wordle", "active_wordle", key="wordle")
_wrap("wordle_guess", "active_wordle", key="wordle")
_wrap("rock_paper_scissors", "leaderboard", key="leaderboard")
_wrap("guess_number", "leaderboard", key="leaderboard")
_wrap("leaderboard_cmd", "leaderboard", key="leaderboard")
