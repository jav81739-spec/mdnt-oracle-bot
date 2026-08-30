"""Lightweight conversational context for the canonical Oracle chat path.

This layer is intentionally deterministic and ephemeral: it enriches the model
request with reply/thread context without creating a second memory store or a
second conversational engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ChatContext:
    """Bounded context extracted from one Telegram message."""

    language: str
    intent_hint: str
    direct_address: bool
    reply_to_name: str
    reply_to_text: str


def analyze_message(text: str, *, direct_address: bool, reply_to_message=None) -> ChatContext:
    """Extract small, safe-to-pass conversational hints from an update."""
    value = (text or "").strip()
    low = value.casefold()
    devanagari = bool(re.search(r"[\u0900-\u097f]", value))
    hindi_markers = ("kya", "kyu", "kyun", "kaise", "haan", "nahi", "bhai", "yaar", "mujhe", "mera", "meri", "tum")
    hindi = devanagari or any(re.search(rf"\b{re.escape(marker)}\b", low) for marker in hindi_markers)
    english = bool(re.search(r"\b(the|is|are|what|why|how|can|will|just|today|feel|felt)\b", low))
    language = "hinglish" if hindi and english else "hindi" if hindi else "english"

    if "?" in value or re.search(r"\b(what|why|how|when|where|who|can|should|kya|kyu|kaise)\b", low):
        intent = "question"
    elif re.search(r"\b(love|like|miss|happy|sad|hurt|angry|stressed|tension|darr|scared|excited|proud)\b", low):
        intent = "emotional"
    elif re.search(r"😂|🤣|💀|lol|haha|lmao|rofl|bruh", low):
        intent = "playful"
    elif re.search(r"\b(finally|done|got it|mil gaya|ho gaya|achieved|won|cleared)\b", low):
        intent = "update"
    else:
        intent = "casual"

    reply_name = ""
    reply_text = ""
    if reply_to_message is not None:
        author = getattr(reply_to_message, "from_user", None)
        reply_name = str(getattr(author, "first_name", "") or "")[:60]
        reply_text = str(
            getattr(reply_to_message, "text", None)
            or getattr(reply_to_message, "caption", None)
            or ""
        ).strip()[:500]

    return ChatContext(language, intent, bool(direct_address), reply_name, reply_text)
