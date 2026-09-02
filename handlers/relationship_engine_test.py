from .relationship_engine import _clean_reading, _reading_text


def test_relationship_reading_rejects_old_robotic_language():
    assert not _clean_reading("The paths cross often enough for the Oracle to notice. The Oracle records patterns. It does not explain them.")
    assert not _clean_reading("The conversational gravity between them is strong enough to matter.")


def test_relationship_caption_has_no_signal_score_or_fixed_ending():
    text = _reading_text(
        "crossing",
        {"username": "one", "name": "One"},
        {"username": "two", "name": "Two"},
        "They keep finding the same small moments in conversation, without either one forcing it.",
    )
    assert "84%" not in text
    assert "records patterns" not in text.casefold()
    assert "does not explain" not in text.casefold()
    assert "@one" in text and "@two" in text
