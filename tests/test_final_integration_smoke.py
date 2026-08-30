import importlib

def test_canonical_modules_import():
    for name in ('midnight_oracle.main','midnight_oracle.friend_engine','handlers.runtime_registry','handlers.legacy_surface'):
        importlib.import_module(name)

def test_telegram_all_types_available():
    from telegram import Update
    assert 'message' in Update.ALL_TYPES
    assert 'callback_query' in Update.ALL_TYPES
    assert 'inline_query' in Update.ALL_TYPES
    assert 'poll' in Update.ALL_TYPES
    assert 'poll_answer' in Update.ALL_TYPES
