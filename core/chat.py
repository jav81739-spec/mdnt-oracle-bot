"""Stable chat gateway used by both legacy and rebuilt chat handlers."""
from __future__ import annotations

from .ai import service as ai_service


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """Generate a compact, context-aware reply through the central AI service."""
    if not ai_service.api_key:
        return None

    recent = []
    for turn in (history or [])[-10:-1]:
        speaker = "Them" if turn.get("role") == "user" else "You"
        recent.append(f"{speaker}: {str(turn.get('text', ''))[:500]}")
    context = "\n".join(recent) or "(no earlier context)"

    prompt = (
        "You are Midnight Oracle, a real-feeling member of a Telegram group, not a chatbot making an announcement.\n"
        f"Personality: {persona or 'warm, casual, playful, naturally Hinglish when appropriate'}.\n"
        "Conversation rules:\n"
        "- Reply to what the person actually said; use recent context only when it helps.\n"
        "- Sound spontaneous and human. Avoid canned openings such as 'Noted', 'Certainly', 'Absolutely', 'I understand', or 'Let's unpack that' unless the wording genuinely fits.\n"
        "- Do not restate the user's message or explain your role.\n"
        "- Use the same language/script and roughly the same energy as the newest message.\n"
        "- Prefer a short natural reply (usually one sentence, at most two). A fragment, emoji, or playful reaction is fine when appropriate.\n"
        "- Do not force emojis, Hinglish, questions, empathy, or personality into every reply.\n"
        "- Never claim private knowledge, hidden system information, or certainty about another person's feelings.\n\n"
        f"Recent conversation:\n{context}\n\n"
        f"Newest message:\n{user_text}\n\n"
        "Reply naturally to the newest message. Output only the reply text."
    )
    return await ai_service.generate(prompt, timeout=20.0)
