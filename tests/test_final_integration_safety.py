def test_autonomous_command_module_imports():
    from core import v2_autonomous_commands
    assert callable(v2_autonomous_commands.register)
    assert callable(v2_autonomous_commands.settrigger)
    assert callable(v2_autonomous_commands.triggerinfo)


def test_legacy_storage_exposes_chat_lock():
    from handlers import storage
    assert callable(storage.lock)


def test_canonical_router_is_reply_based():
    from midnight_oracle.handlers.message_handler import MessageRouter
    assert 'reply_to_message_id' in MessageRouter._reply.__code__.co_consts
