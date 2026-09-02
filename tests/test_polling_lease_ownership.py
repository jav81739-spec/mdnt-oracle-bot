"""Regression tests for polling-lease ownership safety."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

import startup


class FakeStorage:
    def __init__(self):
        self.value = None

    async def get(self, key):
        return self.value

    async def setex(self, key, ttl, value):
        self.value = value
        return True

    async def setnx(self, key, value, ttl=15):
        if self.value is not None:
            return False
        self.value = value
        return True

    async def compare_set(self, key, expected, value, ttl=0):
        if self.value != expected:
            return False
        self.value = value
        return True


class PollingLeaseOwnershipTests(unittest.TestCase):
    def test_stale_heartbeat_cannot_overwrite_new_owner(self):
        async def scenario():
            store = FakeStorage()
            old = json.dumps({"instance": "old-owner", "ts": 1})
            new = json.dumps({"instance": "new-owner", "ts": 2})
            store.value = old
            with patch.object(startup, "_storage", store), patch.object(startup, "_INSTANCE_ID", "old-owner"):
                store.value = new
                refreshed = await startup._refresh_lease(old)
            self.assertFalse(refreshed)
            self.assertEqual(json.loads(store.value)["instance"], "new-owner")

        asyncio.run(scenario())

    def test_current_owner_can_refresh_atomically(self):
        async def scenario():
            store = FakeStorage()
            old = json.dumps({"instance": "owner", "ts": 1})
            store.value = old
            with patch.object(startup, "_storage", store), patch.object(startup, "_INSTANCE_ID", "owner"):
                refreshed = await startup._refresh_lease(old)
            self.assertTrue(refreshed)
            self.assertEqual(json.loads(store.value)["instance"], "owner")
            self.assertNotEqual(store.value, old)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
