import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeRegressionTests(unittest.TestCase):
    def test_readiness_handler_does_not_drive_asyncio(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertNotIn("asyncio.run(", source)
        self.assertIn("_ready_state", source)

    def test_current_gemini_default_is_used(self):
        source = (ROOT / "core" / "ai.py").read_text(encoding="utf-8")
        self.assertIn('"gemini-3.7-flash"', source)
        self.assertNotIn('"gemini-2.0-flash"', source)

    def test_legacy_key_compatibility_uses_scan(self):
        source = (ROOT / "storage.py").read_text(encoding="utf-8")
        self.assertIn("return await storage.scan(pattern)", source)
        self.assertNotIn("storage._request(\"POST\", \"/\", json=[\"KEYS\", pattern])", source)


if __name__ == "__main__":
    unittest.main()
