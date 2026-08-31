"""Freshness governor for Oracle-generated experiences.

Freshness is independent from member memory. It remembers the shape of recent
experiences as well as their exact text, reducing repetition across wording,
structure, theme, media, pair and strategy dimensions.
"""
from __future__ import annotations

import hashlib
import re
from collections import deque
from typing import Any

class FreshnessGovernor:
    def __init__(self, application: Any, max_items: int = 64) -> None:
        self.application = application
        self.max_items = max_items
        self._recent: dict[str, deque[dict[str, str]]] = application.bot_data.setdefault("oracle_freshness", {})

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").casefold())).strip()

    @classmethod
    def fingerprint(cls, kind: str, text: str) -> str:
        normalized = cls._normalize(text)
        return hashlib.sha256(f"{kind}|{normalized}".encode()).hexdigest()[:20]

    @classmethod
    def shape(cls, text: str) -> str:
        normalized = cls._normalize(text)
        words = normalized.split()
        if not words:
            return "empty"
        buckets = (len(words) // 12, min(5, len([p for p in re.split(r"\n+", text or "") if p.strip()])), words[0][:12], words[-1][:12])
        return hashlib.sha256(repr(buckets).encode()).hexdigest()[:16]

    def _items(self, chat_id: int) -> deque[dict[str, str]]:
        return self._recent.setdefault(str(chat_id), deque(maxlen=self.max_items))

    def seen_recently(self, chat_id: int, kind: str, text: str, *, theme: str = "", media: str = "", pair: str = "", strategy: str = "") -> bool:
        fp = self.fingerprint(kind, text)
        shape = self.shape(text)
        for item in self._items(chat_id):
            if item["fp"] == fp:
                return True
            # Reject the same creative skeleton when multiple other dimensions also repeat.
            same_dimensions = sum((item["kind"] == kind, item["shape"] == shape, item["theme"] == theme, item["media"] == media, item["pair"] == pair, item["strategy"] == strategy))
            if same_dimensions >= 4:
                return True
        return False

    def record(self, chat_id: int, kind: str, text: str, *, theme: str = "", media: str = "", pair: str = "", strategy: str = "") -> None:
        self._items(chat_id).append({"fp": self.fingerprint(kind, text), "shape": self.shape(text), "kind": kind, "theme": theme, "media": media, "pair": pair, "strategy": strategy})

    def accept(self, chat_id: int, kind: str, text: str, *, theme: str = "", media: str = "", pair: str = "", strategy: str = "") -> bool:
        if self.seen_recently(chat_id, kind, text, theme=theme, media=media, pair=pair, strategy=strategy):
            return False
        self.record(chat_id, kind, text, theme=theme, media=media, pair=pair, strategy=strategy)
        return True
