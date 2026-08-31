"""Freshness governor for Oracle-generated experiences.

Tracks recent creative fingerprints per group and rejects near-repetition before
anything is delivered. It is intentionally independent from member memory.
"""
from __future__ import annotations
import hashlib
import re
from collections import deque
from typing import Any

class FreshnessGovernor:
    def __init__(self, application: Any, max_items: int = 48) -> None:
        self.application = application
        self.max_items = max_items
        self._recent: dict[str, deque[str]] = application.bot_data.setdefault("oracle_freshness", {})

    @staticmethod
    def fingerprint(kind: str, text: str) -> str:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", (text or "").casefold())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return hashlib.sha256(f"{kind}|{normalized}".encode()).hexdigest()[:20]

    def seen_recently(self, chat_id: int, kind: str, text: str) -> bool:
        fp = self.fingerprint(kind, text)
        return fp in self._recent.setdefault(str(chat_id), deque(maxlen=self.max_items))

    def record(self, chat_id: int, kind: str, text: str) -> None:
        self._recent.setdefault(str(chat_id), deque(maxlen=self.max_items)).append(self.fingerprint(kind, text))

    def accept(self, chat_id: int, kind: str, text: str) -> bool:
        if self.seen_recently(chat_id, kind, text):
            return False
        self.record(chat_id, kind, text)
        return True
