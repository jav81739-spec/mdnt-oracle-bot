def test_owner_menu_contains_recovery_commands():
    from startup import _verify_command_menu
    import inspect
    source = inspect.getsource(_verify_command_menu)
    assert "BotCommandScopeChat" in source
    assert "midnightmap" in source
    assert "recover" in source
