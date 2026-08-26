from __future__ import annotations

import asyncio
import unittest

from core.autonomy import Member, _members, _render_mention
from core.storage import Storage


class AutonomyTests(unittest.TestCase):
    def test_mentions_are_html_escaped_and_clickable(self):
        member = Member(42, "A <night>", None, 1.0)
        self.assertEqual(_render_mention(member), '<a href="tg://user?id=42">A &lt;night&gt;</a>')

    def test_members_filters_stale_and_malformed_records(self):
        async def run():
            store = Storage()
            import core.autonomy as autonomy
            previous = autonomy.storage
            autonomy.storage = store
            try:
                now = __import__("time").time()
                await store.set("autonomy:members:-1", {
                    "1": {"user_id": 1, "name": "Fresh", "seen": now},
                    "2": {"user_id": 2, "name": "Old", "seen": now - 49 * 3600},
                    "bad": {"name": "Broken"},
                })
                members = await _members(-1)
                self.assertEqual([m.user_id for m in members], [1])
            finally:
                autonomy.storage = previous

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
