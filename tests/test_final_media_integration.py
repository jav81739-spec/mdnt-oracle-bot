from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_image_media_is_on_existing_chat_surface():
    chat = read("handlers/chat.py")
    legacy = read("handlers/legacy_surface.py")
    assert "async def image_command" in chat
    assert '"image":"image_command"' in legacy
    assert "send_photo" in chat


def test_media_commands_reply_to_source_message():
    chat = read("handlers/chat.py")
    assert "send_photo(update.effective_chat.id,url,reply_to_message_id=update.effective_message.message_id)" in chat
    assert "send_animation(update.effective_chat.id,url,reply_to_message_id=update.message.message_id" in chat
    assert "send_sticker(update.effective_chat.id,_pick_sticker(str(update.effective_chat.id)),reply_to_message_id=update.message.message_id" in chat


def test_autonomous_trigger_key_is_shared_by_writer_and_reader():
    commands = read("core/v2_autonomous_commands.py")
    runtime = read("midnight_oracle/main.py")
    assert 'KEY_PREFIX = "v2:autonomous:trigger:"' in commands
    assert "v2:autonomous:trigger:{chat.id}" in runtime


def test_chat_uses_canonical_ai_gateway():
    chat = read("handlers/chat.py")
    assert "from core.chat import generate_reply as core_generate_reply" in chat
    assert "from core.ai import" in chat


def test_no_second_scheduler_added_for_autonomous_commands():
    commands = read("core/v2_autonomous_commands.py")
    assert "OracleScheduler" not in commands
    assert "register_jobs" not in commands
