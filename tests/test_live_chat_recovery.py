def test_live_recovery_evidence():
    from pathlib import Path
    main = Path("midnight_oracle/main.py").read_text()
    events = Path("handlers/events.py").read_text()
    recovery = Path("handlers/recovery.py").read_text()
    assert "LIVE_CHAT_DISCOVERY_FAILED" in main
    assert "events.register(app)" in main
    assert "ChatMemberHandler.MY_CHAT_MEMBER" in events
    assert "→ unresolved" in recovery
