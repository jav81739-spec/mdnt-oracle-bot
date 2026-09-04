"""Shared additive media layer for Midnight Oracle.

Text is primary. Media is a contextual accent with cooldowns, small candidate
pools, and graceful provider failure. It must never replace a conversation or
become a spam loop.
"""
from __future__ import annotations
import logging
import random
import time
from collections import defaultdict, deque
from typing import Any

log = logging.getLogger("midnight.media")
MEDIA_COOLDOWN = 18.0
_last_sent: dict[str, float] = defaultdict(float)
_recent_terms: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=5))
TERM_MAP = {
    "laugh": ("funny reaction", "lol", "laughing"),
    "happy": ("celebration", "excited", "happy"),
    "confused": ("confused reaction", "what", "confused"),
    "awkward": ("awkward reaction", "facepalm", "oops"),
    "celebrate": ("celebration", "party", "excited"),
    "sad": ("sad reaction", "crying", "comfort"),
    "shock": ("shocked reaction", "surprised", "what"),
}

def _gif_lookup():
    from handlers.chat import get_gif_url
    return get_gif_url

def _eligible(chat_id: str, now: float | None = None) -> bool:
    now = now or time.monotonic()
    return now - _last_sent[chat_id] >= MEDIA_COOLDOWN

def choose_term(chat_id: str, intent: str | None = None) -> str | None:
    """Choose one contextual GIF search term, or silence."""
    cid = str(chat_id)
    if not _eligible(cid): return None
    candidates = list(TERM_MAP.get((intent or "").casefold(), ()))
    if not candidates: return None
    recent = _recent_terms[cid]
    candidates = [item for item in candidates if item not in recent] or candidates
    if random.random() > 0.35: return None
    term = random.choice(candidates); recent.append(term); return term

def choose_sticker(text: str, kind: str | None = None, part_index: int | None = None) -> str | None:
    """Never invent sticker IDs; contextual StickerHandler owns sticker choice."""
    return None

async def choose_media(subject: str, kind: str | None = None, part_index: int | None = None, *, intent: str | None = None) -> dict[str, Any] | None:
    """Choose one additive GIF for both chat and autonomous pulse callers."""
    term = choose_term(str(subject), intent or kind)
    if not term: return None
    try:
        url = await _gif_lookup()(term)
    except Exception:
        log.exception("GIF_LOOKUP_FAILED | term=%s", term)
        return None
    return {"kind": "gif", "term": term, "url": url} if url else None

async def send_additive_gif(bot, chat_id: int | str, url: str, *, reply_to_message_id: int | None = None) -> bool:
    """Send one GIF only after the text path has already delivered."""
    cid = str(chat_id)
    if not _eligible(cid): return False
    try:
        await bot.send_animation(chat_id=chat_id, animation=url, reply_to_message_id=reply_to_message_id)
        _last_sent[cid] = time.monotonic(); return True
    except Exception:
        log.exception("GIF_SEND_FAILED | chat=%s", chat_id)
        return False

async def send_text_with_optional_gif(bot, chat_id: int | str, text: str, *, term: str | None = None, reply_to_message_id: int | None = None) -> None:
    """Send text first, then optionally one additive GIF."""
    await bot.send_message(chat_id=chat_id, text=text or "☾ Midnight Oracle is here.", reply_to_message_id=reply_to_message_id)
    if term:
        try:
            url = await _gif_lookup()(term)
        except Exception:
            log.exception("GIF_LOOKUP_FAILED | term=%s", term)
            return
        if url: await send_additive_gif(bot, chat_id, url, reply_to_message_id=reply_to_message_id)
