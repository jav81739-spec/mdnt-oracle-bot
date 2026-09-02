"""Regression tests for the shared Midnight Oracle expression boundary."""
from __future__ import annotations

import asyncio

from core import oracle_expression as expression


class _FakeMessage:
    def __init__(self):
        self.calls = []
        self.message_id = 42

    async def reply_text(self, text, *args, **kwargs):
        self.calls.append((text, args, kwargs))
        return text


class _FakeUpdate:
    def __init__(self, message):
        self.effective_message = message
        self.message = message
        self.effective_chat = type("Chat", (), {"title": "Test Room", "type": "supergroup"})()


def test_mechanical_commands_are_never_rewritten():
    raw = "☾ Balance: 1,250 coins"
    assert asyncio.run(expression.render(raw, command="balance")) == raw


def test_protected_facts_survive_generated_expression(monkeypatch):
    async def fake_generate(prompt, timeout=18.0):
        assert "/ship" in prompt
        return "@Alice and @Bob have a surprisingly fun kind of chemistry tonight — 87% feels about right."

    monkeypatch.setattr(expression.service, "generate", fake_generate)
    raw = "🚢 @Alice + @Bob\n\n87% match"
    result = asyncio.run(expression.render(raw, command="ship", context="Test Room"))
    assert "@Alice" in result
    assert "@Bob" in result
    assert "87%" in result


def test_revealing_generated_language_is_rejected(monkeypatch):
    async def fake_generate(prompt, timeout=18.0):
        return "The Oracle records patterns: @Alice + @Bob — 87%"

    monkeypatch.setattr(expression.service, "generate", fake_generate)
    raw = "@Alice + @Bob — 87%"
    result = asyncio.run(expression.render(raw, command="ship"))
    assert "records patterns" not in result.casefold()
    assert result == raw


def test_update_proxy_only_intercepts_text_replies(monkeypatch):
    async def fake_generate(prompt, timeout=18.0):
        return "@Alice just did something unexpectedly funny."

    monkeypatch.setattr(expression.service, "generate", fake_generate)
    message = _FakeMessage()
    update = _FakeUpdate(message)

    async def callback(update, context):
        await update.effective_message.reply_text("@Alice did the thing")

    wrapped = expression.wrap_callback(callback, "ship")
    asyncio.run(wrapped(update, object()))
    assert message.calls
    assert "@Alice" in message.calls[0][0]


def test_mechanical_callback_is_returned_unchanged():
    async def callback(update, context):
        return None

    assert expression.wrap_callback(callback, "balance") is callback
