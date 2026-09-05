import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeRegressionTests(unittest.TestCase):
    def test_readiness_and_top_level_runtime_are_separated(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("build_application", source)
        self.assertIn("_post_init", source)
        self.assertIn("await startup.run(application, redis_client)", source)
        self.assertIn("await _post_shutdown(application)", source)

    def test_runtime_identity_is_not_hardcoded_to_main(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("RENDER_GIT_BRANCH", os.getenv("GIT_BRANCH", "unknown"))', source)
        self.assertNotIn('branch=main', source)

    def test_polling_lease_refresh_is_ownership_safe(self):
        source = (ROOT / "startup.py").read_text(encoding="utf-8")
        self.assertIn("_store_setnx", source)
        self.assertIn("_LEASE_KEY", source)
        self.assertIn("POLLING_LEASE", source)
        self.assertIn("owner", source)
        self.assertIn("_release_lease", source)

    def test_current_gemini_model_contract_is_used(self):
        source = (ROOT / "core" / "ai.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_MODEL = "gemini-3.7-flash"', source)
        self.assertIn('"gemini-3.6-flash"', source)
        self.assertIn('"gemini-3.5-flash"', source)
        self.assertIn('"gemini-3.1-flash-lite"', source)
        self.assertIn('"gemini-2.0-flash"', source)
        self.assertIn("RETIRED_MODELS", source)
        self.assertNotIn('self.model = self.model or "gemini-2.0-flash"', source)

    def test_legacy_key_compatibility_uses_scan(self):
        source = (ROOT / "storage.py").read_text(encoding="utf-8")
        self.assertIn("return await storage.scan(pattern)", source)
        self.assertNotIn("storage._request(\"POST\", \"/\", json=[\"KEYS\", pattern])", source)


if __name__ == "__main__":
    unittest.main()
