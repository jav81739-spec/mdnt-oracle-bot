import os
os.environ["OWNER_ID"]="123456789"
os.environ["TELEGRAM_BOT_TOKEN"]="000000000:TEST_TOKEN_1234567890123456789"
os.environ["DATABASE_URL"]="sqlite:///tmp-midnight-test.db"
os.environ["OPENAI_API_KEY"]="sk-test-12345678901234567890"
os.environ["GIPHY_API_KEY"]="giphy-test-12345678901234567890"
os.environ["STICKER_PACK_NAME"]="test_pack"

def test_recovery_module_imports():
    from handlers.recovery import recover_command, register
    assert callable(recover_command)
    assert callable(register)

def test_owner_gate():
    from handlers.recovery import _allowed
    class U: id=123456789
    class C: type="private"
    class X: effective_user=U(); effective_chat=C()
    assert _allowed(X())

def test_recovery_is_read_only_by_contract():
    from handlers import recovery
    source=open(recovery.__file__, encoding="utf-8").read()
    assert "send_message" not in source
    assert "join_chat" not in source
    assert "add_chat" not in source
