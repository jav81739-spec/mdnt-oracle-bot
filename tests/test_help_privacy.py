from telegram.ext import CommandHandler

from handlers.help_command import _section, _PRIVATE_COMMANDS


class _App:
    handlers = {
        0: [
            CommandHandler("oracle", lambda *_: None),
            CommandHandler("id", lambda *_: None),
            CommandHandler("report", lambda *_: None),
        ]
    }


def test_member_help_never_exposes_private_commands():
    text, _ = _section(0, {"oracle", "id", "report"})
    assert "/oracle" in text
    for command in _PRIVATE_COMMANDS:
        assert f"/{command}" not in text


def test_member_help_only_lists_live_commands():
    text, _ = _section(0, {"oracle"})
    assert "/oracle" in text
    assert "/aura" not in text
