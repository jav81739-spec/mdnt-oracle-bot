from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_contract_requires_both_scores_and_runtime_proof():
    text = (ROOT / "docs" / "100-10-contract.md").read_text(encoding="utf-8")
    normalized = text.casefold()
    assert "engineering 100/100" in normalized
    assert "experience 100/100" in normalized
    assert "final release requires both scores to be 100/100." in normalized
    assert "direct telegram verification" in normalized


def test_completion_matrix_contains_production_and_experience_gates():
    text = (ROOT / "docs" / "100-10-completion-matrix.md").read_text(encoding="utf-8")
    normalized = text.casefold()
    for marker in (
        "production deployment",
        "real telegram smoke tests",
        "command ownership and registration",
        "callback ownership and routing",
        "giphy/media failure handling",
        "sticker failure handling",
        "private/group isolation",
        "secret and prompt leakage prevention",
        "premium onboarding",
        "contextual oracle voice",
    ):
        assert marker in normalized
