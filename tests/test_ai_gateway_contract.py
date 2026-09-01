from core.ai import AIService


def test_gemini_defaults_to_current_stable_model():
    service = AIService(api_key="test")
    assert service.model == "gemini-3.7-flash"
    assert "gemini-3.7-flash" in service.FALLBACK_MODELS
    assert "gemini-3.5-flash-lite" in service.FALLBACK_MODELS


def test_retired_models_are_never_selected_from_configuration():
    service = AIService(api_key="test", model="gemini-3.1-pro-preview")
    assert service.model == service.DEFAULT_MODEL


def test_interactions_output_text_is_preferred():
    assert AIService._extract_interaction_text({"output_text": "hello"}) == "hello"


def test_interactions_steps_text_is_extracted():
    data={"steps":[{"type":"model_output","content":[{"type":"text","text":"midnight"}]}]}
    assert AIService._extract_interaction_text(data) == "midnight"
