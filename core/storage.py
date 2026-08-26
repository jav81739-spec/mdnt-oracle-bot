"""Midnight Oracle storage engine.

One async storage abstraction for Render + Upstash REST. It provides bounded
retries, timeouts, JSON-safe values, atomic increments, short-lived locks, key
scanning, and a process-local fallback when no external database is configured.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import quote

import httpx

log = logging.getLogger("midnight.storage")


class StorageError(RuntimeError):
    """Raised when persistent storage is unavailable or returns bad data."""


class Storage:
    def __init__(self, url: str | None = None, token: str | None = None,
                 timeout: float = 8.0, retries: int = 2) -> None:
        self.url = (url or os.getenv("UPSTASH_REDIS_REST_URL", "")).rstrip("/")
        self.token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        self.timeout = timeout
        self.retries = max(0, retries)
        self._client: httpx.AsyncClient | None = None
        self._local: dict[str, Any] = {}
        self._local_expiry: dict[str, float] = {}
        self._local_lists: dict[str, list[str]] = {}
        self._local_lock = asyncio.Lock()
        self._closed = False

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    async def start(self) -> None:
        if self._client is None and self.configured:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=min(4.0, self.timeout)),
                headers={"Authorization": f"Bearer {self.token}"},
            )

    async def close(self) -> None:
        self._closed = True
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.configured:
            raise StorageError("persistent storage is not configured")
        await self.start()
        assert self._client is not None
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self._client.request(method, f"{self.url}{path}", **kwargs)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("error"):
                    raise StorageError(str(payload["error"]))
                return payload.get("result") if isinstance(payload, dict) else payload
            except (httpx.HTTPError, ValueError, StorageError) as exc:
                last = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(0.15 * (2 ** attempt))
        raise StorageError(f"storage request failed after {self.retries + 1} attempts") from last

    async def get(self, key: str, default: Any = None) -> Any:
        if not self.configured:
            async with self._local_lock:
                expiry = self._local_expiry.get(key)
                if expiry and expiry <= time.time():
                    self._local.pop(key, None)
                    self._local_expiry.pop(key, None)
                return self._local.get(key, default)
        try:
            result = await self._request("GET", f"/get/{quote(key, safe='')}")
            return default if result is None else result
        except StorageError:
            log.exception("GET failed for key=%s", key)
            return default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if not isinstance(value, str) else value
        if not self.configured:
            async with self._local_lock:
                self._local[key] = encoded
                if ttl:
                    self._local_expiry[key] = time.time() + ttl
                else:
                    self._local_expiry.pop(key, None)
            return True
        try:
            await self._request("POST", f"/set/{quote(key, safe='')}", content=encoded)
            if ttl:
                await self._request("POST", f"/expire/{quote(key, safe='')}/{int(ttl)}")
            return True
        except StorageError:
            log.exception("SET failed for key=%s", key)
            return False

    async def setnx(self, key: str, value: str, ttl: int = 15) -> bool:
        """Acquire a short-lived Redis lock with NX + EX semantics."""
        if not self.configured:
            async with self._local_lock:
                expiry = self._local_expiry.get(key, 0)
                if key in self._local and expiry > time.time():
                    return False
                self._local[key] = value
                self._local_expiry[key] = time.time() + ttl
                return True
        try:
            result = await self._request(
                "POST", f"/set/{quote(key, safe='')}/{quote(value, safe='')}?NX=true&EX={int(ttl)}"
            )
            return str(result).upper() in {"OK", "TRUE", "1"}
        except StorageError:
            log.exception("SETNX failed for key=%s", key)
            return False

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        if not self.configured:
            async with self._local_lock:
                count = 0
                for key in keys:
                    if key in self._local:
                        count += 1
                        self._local.pop(key, None)
                        self._local_expiry.pop(key, None)
                    self._local_lists.pop(key, None)
                return count
        try:
            result = await self._request("POST", "/", json=["DEL", *keys])
            return int(result or 0)
        except StorageError:
            log.exception("DELETE failed for keys=%s", keys)
            return 0

    async def incrby(self, key: str, amount: int) -> int:
        if not self.configured:
            async with self._local_lock:
                current = int(self._local.get(key, 0) or 0)
                current += int(amount)
                self._local[key] = str(current)
                return current
        try:
            result = await self._request("POST", f"/incrby/{quote(key, safe='')}/{int(amount)}")
            return int(result)
        except StorageError:
            log.exception("INCRBY failed for key=%s", key)
            raise

    async def scan(self, pattern: str = "*", count: int = 100) -> list[str]:
        """Return matching keys without using the blocking Redis KEYS command."""
        count = max(1, min(int(count), 500))
        if not self.configured:
            async with self._local_lock:
                now = time.time()
                for key, expiry in list(self._local_expiry.items()):
                    if expiry <= now:
                        self._local.pop(key, None)
                        self._local_expiry.pop(key, None)
                keys = set(self._local) | set(self._local_lists)
                return sorted(k for k in keys if fnmatch.fnmatchcase(k, pattern))

        found: list[str] = []
        cursor = "0"
        try:
            while True:
                result = await self._request(
                    "POST", "/", json=["SCAN", cursor, "MATCH", pattern, "COUNT", count]
                )
                if not isinstance(result, list) or len(result) != 2:
                    raise StorageError("invalid SCAN response")
                cursor = str(result[0])
                keys = result[1] or []
                found.extend(str(k) for k in keys)
                if cursor == "0":
                    break
            return found
        except StorageError:
            log.exception("SCAN failed for pattern=%s", pattern)
            return []

    async def lpush(self, key: str, *values: Any) -> int:
        if not values:
            return 0
        if not self.configured:
            async with self._local_lock:
                items = self._local_lists.setdefault(key, [])
                for value in values:
                    items.insert(0, str(value))
                return len(items)
        try:
            result = await self._request("POST", "/", json=["LPUSH", key, *[str(v) for v in values]])
            return int(result or 0)
        except StorageError:
            log.exception("LPUSH failed for key=%s", key)
            raise

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        if not self.configured:
            async with self._local_lock:
                items = self._local_lists.get(key, [])
                if end == -1:
                    return items[start:]
                return items[start:end + 1]
        try:
            result = await self._request("POST", "/", json=["LRANGE", key, int(start), int(end)])
            return list(result or [])
        except StorageError:
            log.exception("LRANGE failed for key=%s", key)
            return []

    async def exists(self, key: str) -> bool:
        if not self.configured:
            return (await self.get(key, None)) is not None or bool(self._local_lists.get(key))
        try:
            result = await self._request("GET", f"/exists/{quote(key, safe='')}")
            return bool(int(result or 0))
        except StorageError:
            return False

    async def ttl(self, key: str) -> int:
        if not self.configured:
            expiry = self._local_expiry.get(key)
            return -1 if not expiry else max(0, int(expiry - time.time()))
        try:
            result = await self._request("GET", f"/ttl/{quote(key, safe='')}")
            return int(result)
        except StorageError:
            return -1

    async def _release_lock(self, key: str, token: str) -> None:
        """Delete only our lock token; never perform GET-then-DEL."""
        if not self.configured:
            async with self._local_lock:
                if self._local.get(key) == token:
                    self._local.pop(key, None)
                    self._local_expiry.pop(key, None)
            return
        script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
        try:
            await self._request("POST", "/", json=["EVAL", script, "1", key, token])
        except StorageError:
            # TTL is intentionally the final safety net.
            log.warning("Could not release lock %s cleanly; TTL will expire it", key)

    @asynccontextmanager
    async def lock(self, name: str, ttl: int = 15, wait: float = 3.0) -> AsyncIterator[bool]:
        key = f"lock:{name}"
        token = uuid.uuid4().hex
        deadline = time.monotonic() + max(0.0, wait)
        acquired = False
        while time.monotonic() <= deadline:
            if await self.setnx(key, token, ttl):
                acquired = True
                break
            await asyncio.sleep(0.05)
        try:
            yield acquired
        finally:
            if acquired:
                await self._release_lock(key, token)


storage = Storage()
