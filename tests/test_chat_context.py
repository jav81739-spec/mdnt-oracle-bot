import unittest

from midnight_oracle.chat_context import analyze_message


class ChatContextTests(unittest.TestCase):
    def test_hinglish_question_is_classified(self):
        context = analyze_message("bhai why is this happening?", direct_address=True)
        self.assertEqual(context.language, "hinglish")
        self.assertEqual(context.intent_hint, "question")
        self.assertTrue(context.direct_address)

    def test_reply_context_is_bounded(self):
        author = type("User", (), {"first_name": "Friend"})()
        message = type(
            "Message",
            (),
            {"from_user": author, "text": "hello " + "x" * 700, "caption": None},
        )()
        context = analyze_message("yes", direct_address=False, reply_to_message=message)
        self.assertEqual(context.reply_to_name, "Friend")
        self.assertEqual(len(context.reply_to_text), 500)

    def test_plain_chat_defaults_to_casual(self):
        context = analyze_message("just sitting here")
        self.assertEqual(context.intent_hint, "casual")
        self.assertEqual(context.language, "english")
        self.assertFalse(context.direct_address)


if __name__ == "__main__":
    unittest.main()
