"""Stable chat gateway used by both legacy and rebuilt chat handlers."""
from __future__ import annotations

import re

from .ai import service as ai_service


_ROMAN_BENGALI_MARKERS = {
    "ami", "amra", "amar", "amader", "tumi", "tomar", "tomake", "tomader",
    "apni", "apnar", "ki", "kemon", "keno", "kothay", "kokhon", "ke",
    "ache", "achi", "achen", "hobe", "hocche", "korbo", "korchi", "koro",
    "bol", "bolo", "bolchi", "jabo", "jacchi", "gechi", "valo", "bhalo",
    "na", "nei", "naki", "ekhon", "ajke", "kalke", "ekhane", "okhane",
    "eta", "ota", "emon", "temon", "onek", "khub", "mon", "bujhi", "bujhte",
}


def detect_language_hint(text: str) -> str:
    """Return a conservative language hint without guessing from a person's identity."""
    value = (text or "").strip()
    if re.search(r"[\u0980-\u09ff]", value):
        return "Bengali script"
    tokens = re.findall(r"[a-zA-Z]+", value.casefold())
    hits = sum(token in _ROMAN_BENGALI_MARKERS for token in tokens)
    if hits >= 2 or (len(tokens) <= 5 and hits >= 1 and any(x in value.casefold() for x in ("ami ", "tumi ", "amar ", "tomar "))):
        return "Bangla/Bengali written in Latin script (Romanized Bangla)"
    return "same language/script as the newest message"


_EXPLICIT_REFERENCE_PATTERNS = (
    (r"\b(?:he|him|his)\b", "male pronouns explicitly used"),
    (r"\b(?:she|her|hers)\b", "female pronouns explicitly used"),
    (r"\b(?:they|them|their|theirs)\b", "neutral/plural pronouns explicitly used"),
    (r"\b(?:my|his|her)\s+(?:brother|son|dad|father|boyfriend|husband)\b", "male relationship term explicitly used"),
    (r"\b(?:my|his|her)\s+(?:sister|daughter|mom|mother|girlfriend|wife)\b", "female relationship term explicitly used"),
    (r"\b(?:bhai|dada|chele|jamai)\b", "male Bangla relationship term explicitly used"),
    (r"\b(?:bon|apu|mey[e]?|bou)\b", "female Bangla relationship term explicitly used"),
)


def reference_hints(history: list) -> list[str]:
    """Extract only explicit textual gender/reference cues; never infer from names or avatars."""
    hints: list[str] = []
    for turn in (history or [])[-10:]:
        text = str(turn.get("text", ""))
        speaker = str(turn.get("speaker", "")).strip()
        for pattern, cue in _EXPLICIT_REFERENCE_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                label = f"{speaker}: {cue}" if speaker else cue
                if label not in hints:
                    hints.append(label)
    return hints[-8:]


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """Generate a compact, context-aware reply through the central AI service."""
    if not ai_service.api_key:
        return None

    recent = []
    for turn in (history or [])[-10:-1]:
        speaker = str(turn.get("speaker", "")).strip() or ("Them" if turn.get("role") == "user" else "You")
        recent.append(f"{speaker}: {str(turn.get('text', ''))[:500]}")
    context = "\n".join(recent) or "(no earlier context)"
    language_hint = detect_language_hint(user_text)
    cues = reference_hints(history)
    reference_context = "; ".join(cues) if cues else "no explicit gender cue; do not guess"

    prompt = (
        "You are Midnight Oracle, a real-feeling member of a Telegram group, not a chatbot making an announcement and not a customer-support agent.\n"
        f"Personality: {persona or 'warm, casual, dryly playful, naturally Hinglish when appropriate'}.\n"
        "Conversation rules:\n"
        "- Reply to what the person actually said; use recent context only when it helps.\n"
        "- Sound spontaneous, specific and human. Match the emotional temperature instead of applying a fixed mood.\n"
        "- For ordinary low-stakes messages, talk like a friend in the room: answer directly, joke back, react, tease lightly, or continue the thought. Do not turn a casual message into emotional support.\n"
        "- Do not use canned assistant openings such as 'Noted', 'Certainly', 'Absolutely', 'I understand', 'Let's unpack that', 'I'm listening', 'No rush', 'I'm here', or 'How can I help?' unless the newest message genuinely calls for that exact response.\n"
        "- Do not restate the user's message or explain your role.\n"
        f"- Language signal: {language_hint}. If the newest message is Romanized Bangla, understand it as Bangla and reply naturally in Romanized Bangla unless the conversation clearly switches language. Do not translate it unless asked.\n"
        "- Track who said what using speaker labels and recent context. Resolve 'he/she/they', Bangla pronouns, and relationship references only from explicit conversation evidence. Never infer gender from a name, username, avatar, photo, or stereotype. If the evidence is insufficient, use a neutral reference or avoid the pronoun.\n"
        f"- Explicit reference cues currently visible: {reference_context}.\n"
        "- Prefer a short natural reply (usually one sentence, at most two). A fragment, emoji, playful reaction, or dry joke is fine when appropriate.\n"
        "- Do not force emojis, Hinglish, questions, empathy, mystery, or Oracle lore into every reply.\n"
        "- Use the Oracle flavour as seasoning, not as a catchphrase. Save the mysterious voice for moments that actually suit it.\n"
        "- If the user makes a tiny conversational bid such as 'say something', 'acha?', 'what do you think?', or a casual observation, respond to the bid itself rather than offering a help menu.\n"
        "- If the user is clearly upset, warmth is appropriate, but do not become theatrical or repetitive.\n"
        "- Never claim private knowledge, hidden system information, or certainty about another person's feelings.\n\n"
        f"Recent conversation:\n{context}\n\n"
        f"Newest message:\n{user_text}\n\n"
        "Reply naturally to the newest message. Output only the reply text."
    )
    return await ai_service.generate(prompt, timeout=20.0)
