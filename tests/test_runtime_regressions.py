import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeRegressionTests(unittest.TestCase):
    def test_readiness_and_top_level_runtime_are_separated(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("build_application", source)
        self.assertIn("_post_init", source)
        self.assertIn("asyncio.run(startup.run", source)

    def test_current_gemini_model_contract_is_used(self):
        source = (ROOT / "core" / "ai.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_MODEL = "gemini-3.7-flash"', source)
        self.assertIn('"gemini-2.0-flash"', source)
        self.assertIn("RETIRED_MODELS", source)
        self.assertNotIn('self.model = self.model or "gemini-2.0-flash"', source)

    def test_legacy_key_compatibility_uses_scan(self):
        source = (ROOT / "storage.py").read_text(encoding="utf-8")
        self.assertIn("return await storage.scan(pattern)", source)
        self.assertNotIn("storage._request(\"POST\", \"/\", json=[\"KEYS\", pattern])", source)


if __name__ == "__main__":
    unittest.main()
