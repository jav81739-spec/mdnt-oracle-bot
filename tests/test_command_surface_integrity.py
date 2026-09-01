"""Regression tests for deterministic command ownership and the premium Help archive."""
from pathlib import Path
from handlers.legacy_surface import _assert_no_duplicate_declarations
from handlers.help_command import ADMIN_ONLY, SECTIONS
ROOT=Path(__file__).resolve().parents[1]

def test_command_ownership_is_unique_for_known_surfaces():
    modules={"friendship":{"slap":"slap","hug":"hug"},"moderation":{"mute":"mute","ban":"ban","kick":"kick"},"economy":{"daily":"daily","balance":"balance"}}
    direct={"deathgame":"deathgame_start","cricket":"cricket_command"};_assert_no_duplicate_declarations(modules,direct)

def test_duplicate_command_owners_fail_fast():
    try:_assert_no_duplicate_declarations({"friendship":{"hug":"hug"},"moderation":{"hug":"hug"}}, {})
    except RuntimeError as exc:assert "COMMAND_OWNER_COLLISION: /hug" in str(exc)
    else:raise AssertionError("duplicate command ownership must fail fast")

def test_kick_is_owned_by_moderation_surface():
    source=(ROOT/"handlers"/"legacy_surface.py").read_text(encoding="utf-8")
    assert '"moderation":{"mute":"mute","unmute":"unmute","ban":"ban","kick":"kick"' in source
    friendship_start=source.index('"friendship":{');friendship_end=source.index('},"fun":',friendship_start)
    assert '"kick"' not in source[friendship_start:friendship_end]

def test_help_sections_are_boxed_command_groups():
    assert len(SECTIONS)==11
    assert all(title and commands for title,commands in SECTIONS)
    assert all(command and command==command.lower() for _,commands in SECTIONS for command in commands)

def test_admin_controls_are_not_member_help_commands():
    listed={command for _,commands in SECTIONS for command in commands};assert not (listed & ADMIN_ONLY)

def test_help_classifies_kick_as_moderation_not_bonds():
    sections=dict(SECTIONS);listed={command for _,commands in SECTIONS for command in commands}
    assert "kick" not in sections["🫂 BONDS"]
    assert "kick" not in ADMIN_ONLY
    assert "kick" not in listed or "kick" not in sections["🫂 BONDS"]
