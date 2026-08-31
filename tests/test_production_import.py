import importlib
import os
import unittest


class ProductionImportTests(unittest.TestCase):
    def test_production_entrypoint_imports_without_starting_services(self):
        os.environ.setdefault("BOT_TOKEN", "test-token")
        module = importlib.import_module("bot")
        self.assertTrue(hasattr(module, "_post_init"))
        self.assertTrue(hasattr(module, "build_application"))
        self.assertTrue(hasattr(module, "_error"))


if __name__ == "__main__":
    unittest.main()
