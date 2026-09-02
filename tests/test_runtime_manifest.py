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

    def test_canonical_runtime_owns_live_surface_registration(self):
        entrypoint=(ROOT/"bot.py").read_text(encoding="utf-8")
        startup=(ROOT/"startup.py").read_text(encoding="utf-8")
        runtime=(ROOT/"midnight_oracle"/"main.py").read_text(encoding="utf-8")
        self.assertIn("build_application", entrypoint)
        self.assertIn("_install_live_runtime_bridges", startup)
        self.assertIn("register_jobs", startup)
        self.assertIn("post_init(_post_init)", runtime)
        self.assertIn("MessageHandler(filters.TEXT & ~filters.COMMAND,_route_message)", runtime)

    def test_no_legacy_redis_fallback_is_used_by_entrypoint(self):
        entrypoint=(ROOT/"bot.py").read_text(encoding="utf-8")
        self.assertNotIn("redis.asyncio", entrypoint)
        self.assertNotIn("Redis(host=", entrypoint)

if __name__ == "__main__":
    unittest.main()
