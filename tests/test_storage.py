import asyncio
import unittest

from handlers.storage import UpstashRedis


class FakeRedis(UpstashRedis):
    def __init__(self):
        super().__init__("https://example.test", "token")
        self.calls = []

    async def _command(self, command, *args):
        self.calls.append((command, args))
        if command == "incrby":
            return "42"
        if command == "lrange":
            return ["a", "b"]
        return "OK"


class StorageAdapterTests(unittest.TestCase):
    def test_set_serializes_structured_values(self):
        redis = FakeRedis()
        asyncio.run(redis.set("profile:1", {"coins": 10}))
        self.assertEqual(redis.calls[-1], ("set", ("profile:1", '{"coins": 10}')))

    def test_atomic_increment_returns_integer(self):
        redis = FakeRedis()
        result = asyncio.run(redis.incrby("coins:1", 5))
        self.assertEqual(result, 42)
        self.assertEqual(redis.calls[-1], ("incrby", ("coins:1", 5)))

    def test_list_round_trip_shape(self):
        redis = FakeRedis()
        result = asyncio.run(redis.lrange("activity:1", 0, -1))
        self.assertEqual(result, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
