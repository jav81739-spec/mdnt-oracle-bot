def test_recover_is_reserved_from_legacy_surface():
    from handlers.legacy_surface import register_legacy_surface
    import inspect
    source = inspect.getsource(register_legacy_surface)
    assert '"recover"' in source
