from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_contract_requires_both_scores_and_runtime_proof():
    text = (ROOT / "docs" / "100-10-contract.md").read_text(encoding="utf-8")
    assert "Engineering 100/100" in text
    assert "Experience 100/100" in text
    assert "Final release requires both scores to be 100/100." in text
    assert "direct Telegram verification" in text


def test_completion_matrix_contains_production_and_experience_gates():
    text = (ROOT / "docs" / "100-10-completion-matrix.md").read_text(encoding="utf-8")
    for marker in (
        "production deployment",
        "real Telegram smoke tests",
        "command ownership and registration",
        "callback ownership and routing",
        "GIPHY/media failure handling",
        "sticker failure handling",
        "private/group isolation",
        "secret and prompt leakage prevention",
        "premium onboarding",
        "contextual Oracle voice",
    ):
        assert marker in text
