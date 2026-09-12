def test_menu_button_is_explicitly_restored():
    from startup import _verify_command_menu
    import inspect
    source = inspect.getsource(_verify_command_menu)
    assert "MenuButtonCommands" in source
    assert "set_chat_menu_button" in source
