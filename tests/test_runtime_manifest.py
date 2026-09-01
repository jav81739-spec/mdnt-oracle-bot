"""Static guardrails for the live production runtime."""
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
        commands=[]
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "CommandHandler" or not node.args: continue
            command=node.args[0]
            if isinstance(command, ast.Constant) and isinstance(command.value,str): commands.append(command.value)
        duplicates=sorted({name for name in commands if commands.count(name)>1})
        self.assertEqual(duplicates, [], f"Duplicate Telegram commands: {duplicates}")

    def test_canonical_runtime_owns_phase_surface_registration(self):
        entrypoint=(ROOT/"bot.py").read_text(encoding="utf-8")
        runtime=(ROOT/"midnight_oracle"/"main.py").read_text(encoding="utf-8")
        self.assertIn("import legacy_bot", entrypoint)
        self.assertIn("build_application", entrypoint)
        self.assertIn("register_legacy_surface", runtime)
        self.assertIn("register_v2_unique", runtime)
        self.assertIn("register_v2_autonomous_commands", runtime)

    def test_no_legacy_redis_fallback_is_used_by_entrypoint(self):
        entrypoint=(ROOT/"bot.py").read_text(encoding="utf-8")
        self.assertNotIn("redis.asyncio", entrypoint)
        self.assertNotIn("Redis(host=", entrypoint)

if __name__ == "__main__":
    unittest.main()
