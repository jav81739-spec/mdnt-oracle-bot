import ast
import pathlib
import unittest


class ProductionEntrypointContractTests(unittest.TestCase):
    def test_entrypoint_owns_single_runtime_wiring(self):
        tree = ast.parse(pathlib.Path('bot.py').read_text(encoding='utf-8'))
        imports_legacy = any(isinstance(node, ast.Import) and any(a.name == 'legacy_bot' for a in node.names) for node in tree.body)
        self.assertTrue(imports_legacy)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertTrue({'Application', 'CommandHandler', 'MessageHandler'}.issubset(names))
        self.assertNotIn('ChatMemberHandler', names)

    def test_legacy_runtime_is_not_named_as_the_production_entrypoint(self):
        text = pathlib.Path('legacy_bot.py').read_text(encoding='utf-8')
        self.assertIn('Application', text)
        self.assertIn('def main', text)


if __name__ == '__main__':
    unittest.main()
