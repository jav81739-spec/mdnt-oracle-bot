import os
import unittest


class RuntimeHardeningTests(unittest.TestCase):
    def test_required_runtime_configuration_is_documented(self):
        self.assertTrue(os.path.exists('.env.example'))
        with open('.env.example', encoding='utf-8') as handle:
            text = handle.read()
        for key in ('BOT_TOKEN', 'GEMINI_API_KEY'):
            self.assertIn(key, text)
            self.assertNotIn('AIza', text)

    def test_no_obvious_secret_literals_in_source(self):
        banned = ('AIzaSy', '123456789:AA')
        roots = ('bot.py', 'main.py', 'handlers', 'core')
        for root in roots:
            if not os.path.exists(root):
                continue
            paths = []
            if os.path.isfile(root):
                paths = [root]
            else:
                for base, _, files in os.walk(root):
                    paths.extend(os.path.join(base, f) for f in files if f.endswith('.py'))
            for path in paths:
                with open(path, encoding='utf-8', errors='ignore') as handle:
                    text = handle.read()
                for marker in banned:
                    self.assertNotIn(marker, text, path)


if __name__ == '__main__':
    unittest.main()
