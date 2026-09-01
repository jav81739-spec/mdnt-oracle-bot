import unittest
from midnight_oracle.voice_triggers import wants_voice


class VoiceTriggerTests(unittest.TestCase):
    def test_explicit_english_triggers(self):
        for text in (
            "send a voice note",
            "send me a voice note",
            "send me a voice",
            "voice mein bolo",
            "say it in voice",
            "send an audio note",
        ):
            with self.subTest(text=text):
                self.assertTrue(wants_voice(text))

    def test_explicit_hinglish_triggers(self):
        for text in (
            "bol ke batao",
            "suna do",
            "awaaz mein bolo",
            "voice me bolo",
            "voice note bhejo",
        ):
            with self.subTest(text=text):
                self.assertTrue(wants_voice(text))

    def test_normal_chat_does_not_trigger(self):
        for text in (
            "what are you doing",
            "good morning",
            "tell me something",
            "I am tired",
            "I have a voice problem",
            "your voice is funny",
            "this audio is broken",
            "bolo kya hua",
            "suno meri baat",
            "voice",
            "audio",
            "speak",
            "say it",
        ):
            with self.subTest(text=text):
                self.assertFalse(wants_voice(text))


if __name__ == "__main__":
    unittest.main()
