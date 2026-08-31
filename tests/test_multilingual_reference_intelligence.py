from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_first_wave_romanized_bangla_is_in_canonical_gateway():
    chat = read("core/chat.py")
    assert "detect_language_hint" in chat
    assert "Romanized Bangla" in chat
    assert "Bangla/Bengali written in Latin script" in chat


def test_reference_resolution_uses_explicit_evidence_only():
    chat = read("core/chat.py")
    assert "reference_hints" in chat
    assert "Never infer gender from a name, username, avatar, photo, or stereotype." in chat
    assert "no explicit gender cue; do not guess" in chat


def test_group_chat_keeps_display_name_context_without_using_identity_ids_for_prompt_context():
    chat = read("handlers/chat.py")
    assert 'getattr(user,"first_name",None)' in chat
    assert '"speaker":speaker' in chat
    assert '"speaker":"Midnight Oracle"' in chat
