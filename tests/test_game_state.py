import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from core.game_state import GameState, GameStateError


class GameStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_rejects_oversized_state(self):
        game = GameState("test", 1)
        with self.assertRaises(GameStateError):
            await game.save({"blob": "x" * 50_000})

    async def test_save_and_load_use_scoped_key(self):
        game = GameState("hangman", 123)
        with patch("core.game_state.storage") as storage:
            storage.save = AsyncMock(return_value=True)
            storage.load = AsyncMock(return_value={"word": "oracle"})
            await game.save({"word": "oracle"})
            loaded = await game.load()
        storage.save.assert_awaited_once_with(game.key, {"word": "oracle"}, ttl=None)
        storage.load.assert_awaited_once_with(game.key, {})
        self.assertEqual(loaded["word"], "oracle")

    async def test_clear_is_scoped(self):
        game = GameState("ttt", 99)
        with patch("core.game_state.storage") as storage:
            storage.delete = AsyncMock(return_value=True)
            await game.clear()
        storage.delete.assert_awaited_once_with("game:ttt:99")


if __name__ == "__main__":
    unittest.main()
