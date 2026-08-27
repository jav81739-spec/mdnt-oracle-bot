import os
import unittest
from unittest.mock import patch

from core.polling_lease_namespace import _namespaced_key


class PollingLeaseNamespaceTests(unittest.TestCase):
    def test_same_token_shares_lease(self):
        key = "midnight:telegram:polling-lease:v2"
        with patch.dict(os.environ, {"BOT_TOKEN": "123:abc"}, clear=False):
            self.assertEqual(_namespaced_key(key), _namespaced_key(key))

    def test_rotated_token_gets_new_namespace(self):
        key = "midnight:telegram:polling-lease:v2"
        with patch.dict(os.environ, {"BOT_TOKEN": "123:old"}, clear=False):
            old = _namespaced_key(key)
        with patch.dict(os.environ, {"BOT_TOKEN": "456:new"}, clear=False):
            new = _namespaced_key(key)
        self.assertNotEqual(old, new)
        self.assertTrue(old.startswith(key + ":"))
        self.assertTrue(new.startswith(key + ":"))

    def test_non_polling_keys_are_untouched(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "123:abc"}, clear=False):
            self.assertEqual(_namespaced_key("midnight:other-key"), "midnight:other-key")

    def test_missing_token_preserves_legacy_key(self):
        with patch.dict(os.environ, {"BOT_TOKEN": ""}, clear=False):
            self.assertEqual(_namespaced_key("midnight:telegram:polling-lease:v2"), "midnight:telegram:polling-lease:v2")


if __name__ == "__main__":
    unittest.main()
