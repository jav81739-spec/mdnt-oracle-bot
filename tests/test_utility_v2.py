import asyncio
import json
import unittest

from core.storage import Storage
from core.utility import _load, _save


class UtilityV2Tests(unittest.TestCase):
    def test_afk_state_round_trips_through_storage(self):
        async def scenario():
            store = Storage()
            import core.utility as utility
            previous = utility.storage
            utility.storage = store
            try:
                state = {"123": "studying", "456": "sleeping"}
                await _save(99, state)
                loaded = await _load(99)
                self.assertEqual(loaded, state)
                raw = await store.get("utility:afk:99")
                self.assertEqual(json.loads(raw), state)
            finally:
                utility.storage = previous

        asyncio.run(scenario())

    def test_empty_afk_state_is_deleted(self):
        async def scenario():
            store = Storage()
            import core.utility as utility
            previous = utility.storage
            utility.storage = store
            try:
                await _save(99, {"123": "away"})
                await _save(99, {})
                self.assertEqual(await store.get("utility:afk:99"), None)
            finally:
                utility.storage = previous

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
