from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generic_callback_handler_has_narrow_routing_pattern():
    source = (ROOT / "midnight_oracle" / "main.py").read_text(encoding="utf-8")
    assert 'CallbackQueryHandler(handle_callback)' not in source
    assert 'CallbackQueryHandler(handle_callback,pattern=r\'^(?:reveal_|secret:).+\')' in source or 'CallbackQueryHandler(handle_callback, pattern=r\'^(?:reveal_|secret:).+\')' in source


def test_callback_handler_does_not_claim_help_or_v2_callbacks():
    source = (ROOT / "midnight_oracle" / "handlers" / "callback_handler.py").read_text(encoding="utf-8")
    assert 'data.startswith("help:")' not in source
    assert 'data.startswith("v2cricket:")' not in source


def test_truth_callbacks_are_registered_and_handled():
    main_source = (ROOT / "midnight_oracle" / "main.py").read_text(encoding="utf-8")
    command_source = (ROOT / "midnight_oracle" / "handlers" / "command_handler.py").read_text(encoding="utf-8")
    assert 'CallbackQueryHandler(truth_callback' in main_source
    assert 'pattern=r"^truth:(?:answer|pass)$"' in main_source
    assert "callback_data='truth:answer'" in command_source
    assert "callback_data='truth:pass'" in command_source
    assert 'async def truth_callback' in command_source
    assert 'if action=="answer"' in command_source
    assert 'elif action=="pass"' in command_source
