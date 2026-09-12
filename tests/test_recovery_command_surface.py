def test_recovery_commands_are_present():
    from midnight_oracle.main import build_application
    app = build_application()
    commands = {str(c).lower().lstrip("/") for hs in app.handlers.values() for h in hs for c in (getattr(h, "commands", None) or ())}
    assert "midnightmap" in commands
    assert "recover" in commands
