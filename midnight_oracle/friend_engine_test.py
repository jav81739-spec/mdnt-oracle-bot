"""Phase 1 unit tests for the Oracle Friend Engine."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from types import SimpleNamespace

from .database import Database, now_ts
from .friend_engine import FriendEngine, GroupContext
from .mood_engine import MoodEngine
from .generators.reply_generator import ReplyGenerator
from .handlers.message_handler import MessageRouter


class FakeReplies:
    """Provide deterministic local replies for engine tests."""
    async def generate(self, *args, **kwargs):
        """Return a stable test reply."""
        return "Haan, suna. 🌙"


class FriendEngineTests(unittest.IsolatedAsyncioTestCase):
    """Verify the eight required Phase 1 behaviours."""

    async def asyncSetUp(self):
        """Create an isolated SQLite database for each test."""
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        await self.db.connect()
        self.engine = FriendEngine(self.db, MoodEngine(), FakeReplies(), seed=1)
        self.message = lambda text, uid=1: SimpleNamespace(text=text, caption=None, from_user=SimpleNamespace(id=uid))

    async def asyncTearDown(self):
        """Close the isolated database."""
        await self.db.close()

    def ctx(self, **kwargs):
        """Build a deterministic group context for tests."""
        base = dict(sender="1", group_id="99", recent_messages=[], hour=14, is_late_night=False, group_name="Test", relationship_tier="regular", sender_name="Javed", now=1000.0)
        base.update(kwargs)
        return GroupContext(**base)

    async def test_tiredness_detection(self):
        """Tired Hinglish messages receive a valid social decision when the random gate allows."""
        engine = FriendEngine(self.db, MoodEngine(), FakeReplies(), seed=1)
        engine.rng.random = lambda: .01
        result = await engine.process_message(self.message("yaar bahut thak gaya aaj"), self.ctx())
        self.assertTrue(result.should_reply)
        self.assertTrue(result.reply_text)

    async def test_celebration_detection(self):
        """Celebration language crosses the engagement threshold."""
        engine = FriendEngine(self.db, MoodEngine(), FakeReplies(), seed=1)
        engine.rng.random = lambda: .01
        result = await engine.process_message(self.message("finally ho gaya bhai"), self.ctx())
        self.assertTrue(result.should_reply)

    async def test_cooldown_blocks(self):
        """A persistent group cooldown blocks the next ambient response."""
        await self.db.set_cooldown("group", "99", "ambient", now_ts() + 99999)
        result = await self.engine.process_message(self.message("yaar thak gaya"), self.ctx())
        self.assertFalse(result.should_reply)
        self.assertEqual(result.reason, "group_cooldown")

    async def test_late_night_tone(self):
        """Late-night emotional messages receive the late-night flag in the generator context."""
        captured = {}
        class Capture:
            async def generate(self, *args):
                """Capture generator arguments and return a test reply."""
                captured["late"] = args[6]
                return "Yahan hoon. ☾"
        engine = FriendEngine(self.db, MoodEngine(), Capture(), seed=1)
        engine.rng.random = lambda: .01
        result = await engine.process_message(self.message("raat ko akela feel ho raha"), self.ctx(hour=1, is_late_night=True))
        self.assertTrue(result.should_reply)
        self.assertTrue(captured["late"])

    async def test_hinglish_input(self):
        """Hinglish emotional input is accepted without translation or normalization loss."""
        engine = FriendEngine(self.db, MoodEngine(), FakeReplies(), seed=1)
        engine.rng.random = lambda: .01
        result = await engine.process_message(self.message("bhai aaj dimag kharab ho gaya"), self.ctx())
        self.assertTrue(result.should_reply)

    async def test_direct_summon_bypass(self):
        """The router excludes command/direct-summon style messages from ambient processing."""
        class ExplodingEngine:
            async def process_message(self, *args):
                """Fail the test if a direct summon reaches ambient processing."""
                raise AssertionError("direct summon entered ambient engine")
        router = MessageRouter(ExplodingEngine(), SimpleNamespace(observe=lambda *a, **k: asyncio.sleep(0)), MoodEngine())
        update = SimpleNamespace(effective_message=SimpleNamespace(text="/oracle help", caption=None), effective_chat=SimpleNamespace(id=99, type="group", title="Test"), effective_user=SimpleNamespace(id=1, first_name="Javed"))
        await router.handle(update, SimpleNamespace())

    async def test_score_threshold_rejection(self):
        """A bland ambient statement below the configured threshold stays silent."""
        result = await self.engine.process_message(self.message("the train leaves at six"), self.ctx())
        self.assertFalse(result.should_reply)
        self.assertEqual(result.reason, "score_below_threshold")

    async def test_hourly_cap(self):
        """The third ambient opportunity in one hour is rejected."""
        engine = FriendEngine(self.db, MoodEngine(), FakeReplies(), seed=1)
        engine.rng.random = lambda: .01
        engine._hourly["99"] = [900.0, 950.0]
        result = await engine.process_message(self.message("finally ho gaya bhai"), self.ctx(now=1000.0))
        self.assertFalse(result.should_reply)
        self.assertEqual(result.reason, "hourly_cap")


if __name__ == "__main__":
    unittest.main()
