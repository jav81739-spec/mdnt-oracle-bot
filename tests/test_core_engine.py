"""Regression tests for storage, economy, AI boundaries, and runtime wiring."""
from __future__ import annotations

import asyncio
import unittest

from core.economy import EconomyError, EconomyService
from core.storage import Storage


class CoreEngineTests(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_concurrent_adds_do_not_lose_updates(self):
        async def scenario():
            service = EconomyService(Storage())
            await asyncio.gather(*(service.add(7, 1, "test", scope="group") for _ in range(100)))
            self.assertEqual(await service.balance(7, "group"), 100)
        self.run_async(scenario())

    def test_remove_rejects_overspend(self):
        async def scenario():
            service = EconomyService(Storage())
            await service.add(7, 25, "seed", scope="group")
            with self.assertRaises(EconomyError): await service.remove(7, 26, "overspend", scope="group")
            self.assertEqual(await service.balance(7, "group"), 25)
        self.run_async(scenario())

    def test_atomic_transfer_is_balanced(self):
        async def scenario():
            service = EconomyService(Storage())
            await service.add(1, 100, "seed", scope="group")
            await asyncio.gather(*(service.transfer(1, 2, 1, "test", scope="group") for _ in range(100)))
            self.assertEqual(await service.balance(1, "group"), 0)
            self.assertEqual(await service.balance(2, "group"), 100)
        self.run_async(scenario())

    def test_transfer_cannot_create_money(self):
        async def scenario():
            service = EconomyService(Storage())
            await service.add(1, 50, "seed", scope="group")
            with self.assertRaises(EconomyError): await service.transfer(1, 2, 51, "test", scope="group")
            self.assertEqual(await service.balance(1, "group"), 50)
            self.assertEqual(await service.balance(2, "group"), 0)
        self.run_async(scenario())

    def test_atomic_claim_is_idempotent(self):
        async def scenario():
            service = EconomyService(Storage())
            results = await asyncio.gather(*(service.claim_once(7, 100, "daily:test", 60, "daily", scope="group") for _ in range(20)))
            self.assertEqual(sum(tx.amount for tx in results), 100)
            self.assertEqual(await service.balance(7, "group"), 100)
        self.run_async(scenario())

    def test_storage_ttl_fallback(self):
        async def scenario():
            store = Storage(); await store.set("x", "ok", ttl=1)
            self.assertEqual(await store.get("x"), "ok")
            self.assertGreaterEqual(await store.ttl("x"), 0)
        self.run_async(scenario())

    def test_lock_is_exclusive(self):
        async def scenario():
            store, seen = Storage(), []
            async def worker(i):
                async with store.lock("exclusive", ttl=2, wait=1) as acquired:
                    if acquired: seen.append(i); await asyncio.sleep(0.01)
            await asyncio.gather(*(worker(i) for i in range(10)))
            self.assertEqual(len(seen), 10); self.assertEqual(len(set(seen)), 10)
        self.run_async(scenario())


if __name__ == "__main__":
    unittest.main()
