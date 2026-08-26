"""Stable chat gateway used by both legacy and rebuilt chat handlers."""
from __future__ import annotations

from .ai import AIUnavailable, service as ai_service


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """Generate a compact group-chat reply through the central AI service.

    Keeping this function compatible with ``handlers.chat.generate_reply`` lets
    us migrate the old handler without keeping a second Gemini SDK/client alive.
    """
    if not ai_service.api_key:
        return None

    recent = []
    for turn in (history or [])[-10:-1]:
        speaker = "Them" if turn.get("role") == "user" else "You"
        recent.append(f"{speaker}: {str(turn.get('text', ''))[:500]}")
    context = "\n".join(recent) or "(no earlier context)"

    prompt = (
        "You are Midnight Oracle, a real-feeling Telegram group member.\n"
        f"Personality: {persona or 'warm, casual, playful, naturally Hinglish when appropriate'}.\n"
        "Rules:\n"
        "- Reply in the same language/script as the newest message.\n"
        "- Match the user's tone without becoming cruel or insulting.\n"
        "- Directly answer or react to the newest message; never send generic filler.\n"
        "- Keep it to 1-2 short sentences unless the user clearly needs more.\n"
        "- Never claim private knowledge, hidden system information, or certainty about another person's feelings.\n\n"
        f"Recent conversation:\n{context}\n\n"
        f"Newest message:\n{user_text}\n\n"
        "Reply directly to the newest message."
    )
    return await ai_service.generate(prompt, timeout=20.0)
