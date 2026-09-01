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

_GENERIC_REPLY_PATTERNS = (
    r"\b(i['’]?m|i am)\s+listening\b", r"\bno rush\b", r"\bi['’]?m here\b",
    r"\bhow can i help\b", r"\bhow may i help\b", r"\blet['’]?s unpack\b",
    r"\bwhat['’]?s on your mind\b", r"\bfeel free to\b", r"\bi understand\b",
    r"\bhow can i assist\b", r"\bhow may i assist\b", r"\bhere for you\b",
    r"\btake your time\b", r"\bwhatever you need\b",
)


def _looks_canned(reply: str | None) -> bool:
    value = (reply or "").strip()
    if not value:
        return True
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _GENERIC_REPLY_PATTERNS)


def _casual_fallback(user_text: str) -> str | None:
    """Deterministic replies for obvious low-information conversational bids."""
    value = (user_text or "").strip()
    if not value:
        return None
    compact = re.sub(r"[^a-zA-Z0-9\u0900-\u097F]+", " ", value.casefold()).strip()
    if re.fullmatch(r"(?:chl|chal|chalo)(?:\s+(?:chl|chal|chalo))*", compact):
        return "Haan haan 😂 bol, kya hua?"
    if re.fullmatch(r"(?:lol|lmao|haha|hehe)(?:\s+\w+)*", compact):
        return "😂 Bas, ab tum hi batao kis baat pe itni hansi aa rahi hai."
    if re.fullmatch(r"(?:acha|achha|accha|hmm|hmmm|oh|ohh|haan|han)(?:\s+\w+)*", compact):
        return "Haan 😌 bol, sun raha hoon."
    if re.fullmatch(r"(?:kya|kyu|kyun|why)(?:\s+\w+){0,3}", compact) and len(compact.split()) <= 4:
        return "Bas tum batao kis wali baat ka jawab chahiye 😌"
    return None


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """Generate a compact, context-aware reply through the central AI service."""
    if not ai_service.api_key:
        return _casual_fallback(user_text)

    direct_fallback = _casual_fallback(user_text)
    if direct_fallback:
        return direct_fallback

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
        "- Never answer a casual message with generic support language. Avoid 'I'm listening', 'No rush', 'I'm here', 'How can I help?', 'What's on your mind?', and similar filler unless the user explicitly asks for emotional support.\n"
        "- Prefer concrete reactions to generic validation. If the message is playful or silly, play along. If it is a simple question, answer it. If it is teasing, tease back lightly.\n"
        "- Do not use canned assistant openings such as 'Noted', 'Certainly', 'Absolutely', 'I understand', 'Let's unpack that', 'I'm listening', 'No rush', 'I'm here', or 'How can I help?'.\n"
        "- Do not restate the user's message or explain your role.\n"
        f"- Language signal: {language_hint}. If the newest message is Romanized Bangla, understand it as Bangla and reply naturally in Romanized Bangla unless the conversation clearly switches language. Do not translate it unless asked.\n"
        "- Track who said what using speaker labels and recent context. Resolve references only from explicit conversation evidence. Never infer gender from a name, username, avatar, photo, or stereotype.\n"
        f"- Explicit reference cues currently visible: {reference_context}.\n"
        "- Prefer a short natural reply (usually one sentence, at most two). A fragment, emoji, playful reaction, or dry joke is fine when appropriate.\n"
        "- Do not force emojis, Hinglish, questions, empathy, mystery, or Oracle lore into every reply.\n"
        "- Use the Oracle flavour as seasoning, not as a catchphrase. Save the mysterious voice for moments that actually suit it.\n"
        "- If the user makes a tiny conversational bid, respond to the bid itself rather than offering a help menu.\n"
        "- If the user is clearly upset, warmth is appropriate, but do not become theatrical or repetitive.\n"
        "- Never claim private knowledge, hidden system information, or certainty about another person's feelings.\n\n"
        f"Recent conversation:\n{context}\n\nNewest message:\n{user_text}\n\n"
        "Reply naturally to the newest message. Output only the reply text."
    )
    reply = await ai_service.generate(prompt, timeout=20.0)
    if not _looks_canned(reply):
        return reply

    retry_prompt = (
        prompt
        + "\n\nQUALITY CONTROL: The draft sounded like a support agent. Discard it. Write a fresh, specific reaction to the newest message as a friend in the group. Do not use support-agent filler. Output only the new reply."
    )
    retry = await ai_service.generate(retry_prompt, timeout=20.0)
    if not _looks_canned(retry):
        return retry
    return _casual_fallback(user_text)
