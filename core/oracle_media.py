"""Context-aware media companion for Midnight Oracle.

Media is deliberately sparse: it appears only when the moment gives it a
reason. Text stays primary, direct media commands stay explicit, and optional
lookups never become a delivery requirement.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import os
import random
import re
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

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

_ORIGINAL_GIF_LINES = {
    "gossip": (
        "Okay… keep going.",
        "Wait. That's not the whole story.",
        "Don't leave it there.",
        "Now you've got my attention.",
        "You can't end it there.",
        "Hmm. Continue.",
    ),
    "story": (
        "Hmm… that detail matters.",
        "Okay. I'm following this.",
        "There's more in that.",
        "Wait… I caught that.",
        "Now that's interesting.",
    ),
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
        if has_reaction and roll < 0.30:
            return "gif"
        if part_index == 1 and has_visual and roll < 0.55:
            return "image"
        if has_visual and roll < 0.24:
            return "image"
    elif narrative_kind == "gossip":
        if has_reaction and roll < 0.40:
            return "gif"
    elif narrative_kind == "chat":
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


def _original_gif_line(text: str, narrative_kind: str, part_index: int | None) -> str:
    lines = _ORIGINAL_GIF_LINES.get(narrative_kind, _ORIGINAL_GIF_LINES["gossip"])
    return _stable_rng("original-gif-line", narrative_kind, part_index or 0, text[:240]).choice(lines)


def build_original_gif(text: str, narrative_kind: str, part_index: int | None = None) -> BytesIO:
    """Create a small original reaction GIF with Midnight-written words."""
    phrase = _original_gif_line(text, narrative_kind, part_index)
    width, height = 720, 360
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 42)
    small = ImageFont.truetype(font_path, 22)
    frames = []
    for index in range(6):
        image = Image.new("RGB", (width, height), (15, 22, 31))
        draw = ImageDraw.Draw(image)
        pulse = 10 + index * 2 if index <= 3 else 16 - (index - 3) * 2
        draw.ellipse((54 - pulse, 54 - pulse, 118 + pulse, 118 + pulse), fill=(235, 214, 138))
        draw.ellipse((78 - pulse // 2, 47 - pulse // 2, 128 + pulse // 2, 98 + pulse // 2), fill=(15, 22, 31))
        for star in ((180, 70), (590, 82), (640, 260), (100, 285), (530, 55)):
            r = 2 + ((index + star[0]) % 3)
            draw.ellipse((star[0] - r, star[1] - r, star[0] + r, star[1] + r), fill=(220, 224, 228))
        bbox = draw.multiline_textbbox((0, 0), phrase, font=font, spacing=8, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (width - tw) / 2
        y = 150 + (2 if index in (1, 2, 4) else 0)
        draw.rounded_rectangle((x - 28, y - 22, x + tw + 28, y + th + 22), radius=24, fill=(29, 40, 52), outline=(87, 101, 116), width=2)
        draw.multiline_text((x, y), phrase, font=font, fill=(246, 247, 244), spacing=8, align="center")
        draw.text((width - 180, height - 44), "— Midnight Oracle", font=small, fill=(170, 178, 188))
        frames.append(image)
    output = BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=130, loop=0, optimize=True)
    output.seek(0)
    return output


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
    """Return at most one useful companion; autonomous story/gossip GIFs are original."""
    kind = _media_kind(text, narrative_kind, part_index)
    if not kind:
        return None
    if kind == "gif" and narrative_kind in {"story", "gossip"}:
        return {"kind": "gif", "source": "original", "text": text, "part_index": part_index}
    term = _term(text, narrative_kind)
    url = await (_giphy(term) if kind == "gif" else _wikimedia(term))
    if not url:
        return None
    return {"kind": kind, "url": url, "source": "provider"}
