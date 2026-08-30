"""Regression tests for deterministic command ownership and the premium Help archive."""

from handlers.legacy_surface import _assert_no_duplicate_declarations
from handlers.help_command import ADMIN_ONLY, SECTIONS


def test_command_ownership_is_unique_for_known_surfaces():
    modules = {
        "friendship": {"kick": "kick", "slap": "slap", "hug": "hug"},
        "moderation": {"mute": "mute", "ban": "ban"},
        "economy": {"daily": "daily", "balance": "balance"},
    }
    direct = {"deathgame": "deathgame_start", "cricket": "cricket_command"}
    _assert_no_duplicate_declarations(modules, direct)


def test_duplicate_command_owners_fail_fast():
    modules = {"friendship": {"hug": "hug"}, "moderation": {"hug": "hug"}}
    try:
        _assert_no_duplicate_declarations(modules, {})
    except RuntimeError as exc:
        assert "COMMAND_OWNER_COLLISION: /hug" in str(exc)
    else:
        raise AssertionError("duplicate command ownership must fail fast")


def test_help_sections_are_boxed_command_groups():
    assert len(SECTIONS) == 11
    assert all(title and commands for title, commands in SECTIONS)
    assert all(command and command == command.lower() for _, commands in SECTIONS for command in commands)


def test_admin_controls_are_not_member_help_commands():
    listed = {command for _, commands in SECTIONS for command in commands}
    assert not (listed & ADMIN_ONLY)
