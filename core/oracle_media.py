"""Context-aware media companion for autonomous Oracle narratives.

Media is deliberately sparse: one optional companion at most, with a durable
per-group cooldown supplied by the caller. Text remains the primary experience.
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


def _term(text: str, kind: str) -> str:
    value = re.sub(r"[^\w\s'-]", " ", text or "", flags=re.UNICODE)
    words = [w for w in value.split() if len(w) > 2]
    stop = {
        "part", "the", "and", "with", "that", "this", "from", "then",
        "when", "there", "someone", "nobody", "oracle", "room", "had",
        "forgotten", "first", "clue",
    }
    meaningful = [w for w in words if w.casefold() not in stop]
    base_words = meaningful[:4] or words[:4]
    base = " ".join(base_words)[:48].strip()
    if kind == "story":
        return f"cinematic {base} night"[:72].strip()
    return f"curious {base}"[:72].strip()


def _stable_rng(*values: str | int | None) -> random.Random:
    seed = "|".join(str(v or "") for v in values).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _media_kind(text: str, narrative_kind: str, part_index: int | None) -> str | None:
    """Choose a restrained medium; never force media into every narrative."""
    low = (text or "").casefold()
    rng = _stable_rng(narrative_kind, part_index or 0, low[:160])
    roll = rng.random()
    if narrative_kind == "story":
        if roll < 0.18 and part_index == 1:
            return "image"
        if roll < 0.30 and any(x in low for x in ("train", "city", "library", "star", "ocean", "map", "street", "rain", "moon")):
            return "image"
    elif narrative_kind == "gossip":
        if roll < 0.12 and any(x in low for x in ("funny", "ridiculous", "rumour", "rumor", "weird", "wild", "absurd")):
            return "gif"
    return None


def sticker_ids() -> list[str]:
    raw = os.getenv("ORACLE_STICKER_IDS", "").strip()
    return [x.strip() for x in re.split(r"[,\n]", raw) if x.strip()]


def choose_sticker(text: str, narrative_kind: str, part_index: int | None = None) -> str | None:
    """Use an explicitly configured sticker pack only when a reaction beat fits."""
    ids = sticker_ids()
    if not ids:
        return None
    low = (text or "").casefold()
    if not any(x in low for x in ("😂", "🤣", "funny", "ridiculous", "absurd", "wild", "oh", "wait")):
        return None
    return _stable_rng("sticker", narrative_kind, part_index or 0, low[:120]).choice(ids)


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
