import os
import unittest
from unittest.mock import patch

from core.broadcast import _is_owner, install


class _FakeApplication:
    def __init__(self):
        self.handlers = []

    def add_handler(self, handler, group=0):
        self.handlers.append((handler, group))


class _User:
    def __init__(self, user_id):
        self.id = user_id


class _Update:
    def __init__(self, user_id):
        self.effective_user = _User(user_id)


class BroadcastHardeningTests(unittest.IsolatedAsyncioTestCase):
    def test_install_is_idempotent(self):
        app = _FakeApplication()
        install(app)
        install(app)
        self.assertEqual(len(app.handlers), 2)
        self.assertTrue(getattr(app, "_midnight_broadcast_installed"))

    def test_only_owner_can_broadcast(self):
        with patch.dict(os.environ, {"OWNER_ID": "12345"}, clear=False):
            self.assertTrue(_is_owner(_Update(12345)))
            self.assertFalse(_is_owner(_Update(54321)))

    def test_multiple_owner_ids_supported(self):
        with patch.dict(os.environ, {"OWNER_ID": "12345,67890"}, clear=False):
            self.assertTrue(_is_owner(_Update(67890)))
            self.assertFalse(_is_owner(_Update(99999)))


if __name__ == "__main__":
    unittest.main()
