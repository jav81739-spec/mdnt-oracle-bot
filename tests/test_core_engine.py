"""Fast, dependency-light tests for Midnight's new core engine."""
from __future__ import annotations

import asyncio
import unittest

from core.economy import EconomyService, EconomyError
from core.storage import Storage


class CoreEngineTests(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_concurrent_adds_do_not_lose_updates(self):
        async def scenario():
            store = Storage()
            service = EconomyService(store)
            await asyncio.gather(*(service.add(7, 1, "test", scope="group") for _ in range(100)))
            self.assertEqual(await service.balance(7, "group"), 100)

        self.run_async(scenario())

    def test_remove_rejects_overspend(self):
        async def scenario():
            store = Storage()
            service = EconomyService(store)
            await service.add(7, 25, "seed", scope="group")
            with self.assertRaises(EconomyError):
                await service.remove(7, 26, "overspend", scope="group")
            self.assertEqual(await service.balance(7, "group"), 25)

        self.run_async(scenario())

    def test_transfer_is_balanced(self):
        async def scenario():
            store = Storage()
            service = EconomyService(store)
            await service.add(1, 100, "seed", scope="group")
            await service.transfer(1, 2, 40, "test", scope="group")
            self.assertEqual(await service.balance(1, "group"), 60)
            self.assertEqual(await service.balance(2, "group"), 40)

        self.run_async(scenario())

    def test_storage_ttl_fallback(self):
        async def scenario():
            store = Storage()
            await store.set("x", "ok", ttl=1)
            self.assertEqual(await store.get("x"), "ok")
            self.assertGreaterEqual(await store.ttl("x"), 0)

        self.run_async(scenario())


if __name__ == "__main__":
    unittest.main()
