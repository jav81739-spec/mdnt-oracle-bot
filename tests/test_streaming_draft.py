import asyncio

from handlers.streaming_draft import TelegramDraftStream


class FakeBot:
    def __init__(self):
        self.calls = []

    async def _post(self, method, *, data):
        self.calls.append((method, data))
        return True


def test_draft_stream_throttles_small_updates():
    async def run():
        bot = FakeBot()
        stream = TelegramDraftStream(bot, 123, 7)
        assert await stream.thinking() is True
        assert bot.calls[-1][0] == "sendMessageDraft"
        assert bot.calls[-1][1]["text"] == "Thinking…"
        assert bot.calls[-1][1]["text"]
        assert bot.calls[-1][1]["can_stop"] is True

        assert await stream.push("short") is False
        assert len(bot.calls) == 1

        assert await stream.push("This is enough new text to publish the draft.", force=True) is True
        assert len(bot.calls) == 2
        assert bot.calls[-1][1]["draft_id"] == 7

    asyncio.run(run())


def test_draft_stream_truncates_to_telegram_limit():
    async def run():
        bot = FakeBot()
        stream = TelegramDraftStream(bot, 123, 9)
        text = "x" * 5000
        assert await stream.push(text, force=True) is True
        assert len(bot.calls[-1][1]["text"]) == 4096

    asyncio.run(run())
