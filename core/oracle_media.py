"""Context-aware media companion for autonomous Oracle narratives.

Media is deliberately sparse: one optional companion at most, with a durable
per-group cooldown supplied by the caller. Text remains the primary experience.
"""
from __future__ import annotations

import os
import random
import re
from typing import Any

import httpx

from midnight_oracle.utils.logger import get_logger

log = get_logger("midnight.oracle_media")

MEDIA_COOLDOWN = 12 * 3600


def _term(text: str, kind: str) -> str:
    value = re.sub(r"[^\w\s'-]", " ", text or "", flags=re.UNICODE)
    words = [w for w in value.split() if len(w) > 2]
    base = " ".join(words[:12])
    if kind == "story":
        return f"cinematic {base} night"[:120]
    return f"curious {base}"[:120]


def _media_kind(text: str, narrative_kind: str, part_index: int | None) -> str | None:
    """Choose a restrained medium; never force media into every narrative."""
    low = (text or "").casefold()
    rng = random.Random(hash((narrative_kind, part_index or 0, low[:80])) & 0xFFFFFFFF)
    # Text-first policy: most narrative beats remain text-only.
    roll = rng.random()
    if narrative_kind == "story":
        if roll < 0.18 and part_index in (1, None):
            return "image"
        if roll < 0.28 and any(x in low for x in ("train", "city", "library", "star", "ocean", "map")):
            return "image"
    elif narrative_kind == "gossip":
        if roll < 0.12 and any(x in low for x in ("funny", "ridiculous", "rumour", "rumor", "weird")):
            return "gif"
    return None


async def _giphy(term: str) -> str | None:
    key = os.getenv("GIPHY_API_KEY", "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://api.giphy.com/v1/gifs/search",
                params={"api_key": key, "q": term, "limit": 8, "rating": "pg-13"},
            )
            response.raise_for_status()
            data = response.json().get("data", [])
        urls = [
            item.get("images", {}).get("original", {}).get("url")
            for item in data
            if item.get("images", {}).get("original", {}).get("url")
        ]
        return random.choice(urls) if urls else None
    except Exception:
        log.exception("ORACLE_MEDIA_GIF_LOOKUP_FAILED")
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
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": term,
                    "gsrnamespace": 6,
                    "gsrlimit": 10,
                    "prop": "imageinfo",
                    "iiprop": "url|mime",
                    "iiurlwidth": 1200,
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
        return random.choice(urls) if urls else None
    except Exception:
        log.exception("ORACLE_MEDIA_IMAGE_LOOKUP_FAILED")
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
