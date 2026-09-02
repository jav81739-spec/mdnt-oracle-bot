"""Context-aware media companion for Midnight Oracle.

Media is deliberately sparse: it appears only when the moment gives it a
reason. Text stays primary, direct media commands stay explicit, and optional
lookups never become a delivery requirement.
"""
from __future__ import annotations

import hashlib
import os
import random
import re
from typing import Any

import httpx

from midnight_oracle.utils.logger import get_logger

log = get_logger("midnight.oracle_media")

MEDIA_COOLDOWN = 12 * 3600
CHAT_MEDIA_COOLDOWN = 6 * 3600
COMMAND_MEDIA_COOLDOWN = 0

_VISUAL_CUES = {
    "moon", "night", "rain", "storm", "ocean", "sea", "mountain", "forest",
    "city", "street", "train", "station", "library", "book", "star", "stars",
    "sky", "sunset", "sunrise", "flower", "flowers", "coffee", "tea", "cricket",
    "football", "stadium", "match", "movie", "film", "concert", "travel", "beach",
}
_REACTION_CUES = {
    "😂", "🤣", "😭", "🥲", "lol", "lmao", "haha", "funny", "ridiculous", "absurd",
    "wild", "wtf", "bruh", "oops", "congrats", "congratulations", "damn",
}


def _term(text: str, kind: str) -> str:
    value = re.sub(r"[^\w\s'-]", " ", text or "", flags=re.UNICODE)
    words = [w for w in value.split() if len(w) > 2]
    stop = {
        "part", "the", "and", "with", "that", "this", "from", "then", "when",
        "there", "someone", "nobody", "oracle", "room", "had", "forgotten",
        "first", "clue", "really", "just", "like", "what", "about", "because",
    }
    meaningful = [w for w in words if w.casefold() not in stop]
    base_words = meaningful[:4] or words[:4]
    base = " ".join(base_words)[:48].strip()
    if kind == "story":
        return f"cinematic {base} night"[:72].strip()
    if kind == "chat":
        return f"{base} natural reaction"[:72].strip()
    return f"curious {base}"[:72].strip()


def _stable_rng(*values: str | int | None) -> random.Random:
    seed = "|".join(str(v or "") for v in values).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _media_kind(text: str, narrative_kind: str, part_index: int | None) -> str | None:
    """Choose one restrained medium from the actual conversational beat."""
    low = (text or "").casefold()
    words = set(re.findall(r"[\w]+", low, flags=re.UNICODE))
    has_visual = bool(words & _VISUAL_CUES)
    has_reaction = any(cue in low for cue in _REACTION_CUES)
    rng = _stable_rng(narrative_kind, part_index or 0, low[:240])
    roll = rng.random()

    if narrative_kind == "story":
        if part_index == 1 and has_visual and roll < 0.55:
            return "image"
        if has_visual and roll < 0.24:
            return "image"
    elif narrative_kind == "gossip":
        if has_reaction and roll < 0.22:
            return "gif"
    elif narrative_kind == "chat":
        # Ordinary chat gets media only when the content itself supplies a visual
        # or reaction beat. A long-running chat cannot accumulate media spam.
        if has_reaction and roll < 0.16:
            return "gif"
        if has_visual and roll < 0.12:
            return "image"
    elif narrative_kind == "command":
        if has_reaction and roll < 0.75:
            return "gif"
        if has_visual and roll < 0.55:
            return "image"
    return None


def sticker_ids() -> list[str]:
    raw = os.getenv("ORACLE_STICKER_IDS", "").strip()
    return [x.strip() for x in re.split(r"[,\n]", raw) if x.strip()]


def choose_sticker(text: str, narrative_kind: str, part_index: int | None = None) -> str | None:
    """Use the curated sticker pack only when the beat genuinely calls for it."""
    ids = sticker_ids()
    if not ids:
        return None
    low = (text or "").casefold()
    if not any(cue in low for cue in _REACTION_CUES):
        return None
    return _stable_rng("sticker", narrative_kind, part_index or 0, low[:180]).choice(ids)


async def _giphy(term: str) -> str | None:
    key = os.getenv("GIPHY_API_KEY", "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://api.giphy.com/v1/gifs/search",
                params={"api_key": key, "q": term[:72], "limit": 8, "rating": "pg-13"},
            )
            response.raise_for_status()
            data = response.json().get("data", [])
        urls = [
            item.get("images", {}).get("original", {}).get("url")
            for item in data
            if item.get("images", {}).get("original", {}).get("url")
        ]
        return _stable_rng("giphy", term).choice(urls) if urls else None
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("ORACLE_MEDIA_GIF_LOOKUP_SKIPPED | reason=%s", type(exc).__name__)
        return None


async def _wikimedia(term: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "MidnightOracle/1.0 (contextual-media)"},
        ) as client:
            response = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query", "format": "json", "generator": "search",
                    "gsrsearch": term, "gsrnamespace": 6, "gsrlimit": 10,
                    "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 1200,
                },
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
        urls = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            mime = str(info.get("mime", ""))
            url = info.get("thumburl") or info.get("url")
            if url and mime.startswith("image/") and mime not in {"image/svg+xml", "image/gif"}:
                urls.append(url)
        return _stable_rng("image", term).choice(urls) if urls else None
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("ORACLE_MEDIA_IMAGE_LOOKUP_SKIPPED | reason=%s", type(exc).__name__)
        return None


async def choose_media(text: str, narrative_kind: str, part_index: int | None = None) -> dict[str, Any] | None:
    """Return at most one useful companion; never make media a delivery requirement."""
    kind = _media_kind(text, narrative_kind, part_index)
    if not kind:
        return None
    term = _term(text, narrative_kind)
    url = await (_giphy(term) if kind == "gif" else _wikimedia(term))
    if not url:
        return None
    return {"kind": kind, "url": url}
