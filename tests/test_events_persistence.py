import ast
import pathlib
import unittest


class EventPersistenceTests(unittest.TestCase):
    def test_events_module_uses_durable_storage_and_no_process_state_globals(self):
        path = pathlib.Path('handlers/events.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        source = path.read_text(encoding='utf-8')
        self.assertIn('from core.storage import storage', source)
        self.assertIn('STORAGE_KEY = "events:v2"', source)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                value = node.value
                self.assertFalse(isinstance(value, (ast.Dict, ast.List, ast.Set)), ast.unparse(node))

    def test_event_log_is_explicitly_bounded(self):
        source = pathlib.Path('handlers/events.py').read_text(encoding='utf-8')
        self.assertIn('[-99:] + [user.first_name]', source)


if __name__ == '__main__':
    unittest.main()
