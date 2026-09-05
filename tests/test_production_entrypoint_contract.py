import ast
import pathlib
import unittest


class ProductionEntrypointContractTests(unittest.TestCase):
    def test_entrypoint_delegates_to_single_canonical_runtime(self):
        tree = ast.parse(pathlib.Path('bot.py').read_text(encoding='utf-8'))
        imports_legacy = any(
            isinstance(node, ast.Import)
            and any(a.name == 'legacy_bot' for a in node.names)
            for node in tree.body
        )
        self.assertFalse(imports_legacy)
        imported_from_telegram = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == 'telegram.ext'
            for alias in node.names
        }
        self.assertIn('Application', imported_from_telegram)
        source = pathlib.Path('bot.py').read_text(encoding='utf-8')
        self.assertIn('build_application as _canonical_build_application', source)
        self.assertIn('await startup.run(application, redis_client)', source)
        self.assertIn('await _post_shutdown(application)', source)
        self.assertNotIn('import legacy_bot', source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertNotIn('ChatMemberHandler', names)

    def test_legacy_runtime_is_not_named_as_the_production_entrypoint(self):
        text = pathlib.Path('legacy_bot.py').read_text(encoding='utf-8')
        self.assertIn('Application', text)
        self.assertIn('def main', text)


if __name__ == '__main__':
    unittest.main()
