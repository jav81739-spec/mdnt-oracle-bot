"""Static guardrails for the staged legacy runtime.

These tests make the remaining monolith measurable while handlers are migrated
out of it. They intentionally do not execute Telegram startup or call external
services.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy_bot.py"


class RuntimeManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(LEGACY.read_text(encoding="utf-8"), filename=str(LEGACY))

    def test_command_handlers_have_unique_names(self):
        commands: list[str] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "CommandHandler":
                continue
            if not node.args:
                continue
            command = node.args[0]
            if isinstance(command, ast.Constant) and isinstance(command.value, str):
                commands.append(command.value)
        duplicates = sorted({name for name in commands if commands.count(name) > 1})
        self.assertEqual(duplicates, [], f"Duplicate Telegram commands: {duplicates}")

    def test_production_entrypoint_is_thin_bridge(self):
        entrypoint = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("import legacy_bot", entrypoint)
        self.assertIn("legacy_bot._addcoins", entrypoint)
        self.assertIn("legacy_bot._generate_gemini", entrypoint)
        self.assertIn("legacy_bot._start_dummy_server", entrypoint)

    def test_no_legacy_redis_fallback_is_used_by_entrypoint(self):
        entrypoint = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertNotIn("redis.asyncio", entrypoint)
        self.assertNotIn("Redis(host=", entrypoint)


if __name__ == "__main__":
    unittest.main()
