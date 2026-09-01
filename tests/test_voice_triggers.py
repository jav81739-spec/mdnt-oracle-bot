import unittest
from midnight_oracle.voice_triggers import wants_voice


class VoiceTriggerTests(unittest.TestCase):
    def test_explicit_english_triggers(self):
        for text in ("send a voice note", "voice mein bolo", "say it", "audio bhejo"):
            with self.subTest(text=text):
                self.assertTrue(wants_voice(text))

    def test_explicit_hinglish_triggers(self):
        for text in ("bol ke bata", "sunao", "awaaz mein", "voice me"):
            with self.subTest(text=text):
                self.assertTrue(wants_voice(text))

    def test_normal_chat_does_not_trigger(self):
        for text in ("what are you doing", "good morning", "tell me something", "I am tired"):
            with self.subTest(text=text):
                self.assertFalse(wants_voice(text))


if __name__ == "__main__":
    unittest.main()
