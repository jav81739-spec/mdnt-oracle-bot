"""Small Redis/Upstash REST lease used to elect one Telegram poller.

Uses the repository's existing httpx dependency; no new package is required.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid

import httpx


class TelegramPollerLease:
    def __init__(self, ttl: int = 120) -> None:
        self.ttl = max(30, int(ttl))
        token = os.getenv("BOT_TOKEN", "")
        self.key = "midnight:v2:telegram-poller:" + hashlib.sha256(token.encode()).hexdigest()[:24]
        self.owner = f"{os.getenv('RENDER_INSTANCE_ID') or os.getenv('RENDER_SERVICE_ID') or os.getpid()}:{uuid.uuid4().hex}"
        self.url = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
        self.auth = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._client: httpx.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self.url and self.auth)

    def _request(self, command: list[str]):
        if not self.configured:
            return None
        if self._client is None:
            self._client = httpx.Client(timeout=4.0, headers={"Authorization": f"Bearer {self.auth}"})
        response = self._client.post(self.url, json=command)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload.get("result") if isinstance(payload, dict) else payload

    def acquire(self) -> bool:
        if not self.configured:
            return True
        try:
            result = self._request(["SET", self.key, self.owner, "NX", "EX", str(self.ttl)])
            return str(result).upper() in {"OK", "TRUE", "1"}
        except Exception:
            return False

    def _renew(self) -> None:
        script = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('EXPIRE', KEYS[1], ARGV[2]) else return 0 end"
        while not self._stop.wait(max(10, self.ttl // 3)):
            try:
                result = self._request(["EVAL", script, "1", self.key, self.owner, str(self.ttl)])
                if int(result or 0) != 1:
                    self._stop.set()
                    return
            except Exception:
                # A transient storage outage must not immediately kill the bot.
                # The lease naturally expires if ownership cannot be renewed.
                continue

    def start(self) -> bool:
        if not self.acquire():
            return False
        if self.configured:
            self._thread = threading.Thread(target=self._renew, daemon=True, name="telegram-poller-lease")
            self._thread.start()
        return True

    def release(self) -> None:
        self._stop.set()
        if not self.configured:
            return
        script = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end"
        try:
            self._request(["EVAL", script, "1", self.key, self.owner])
        except Exception:
            pass
        finally:
            if self._client is not None:
                self._client.close()
                self._client = None
