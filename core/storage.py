"""Durable async storage for Midnight Oracle.

Production uses Upstash Redis REST; tests/development use a deterministic
in-process fallback. Network operations are bounded and retried. Distributed
locks use random tokens and server-side compare-and-delete.
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
    """Raised when a required persistent operation cannot be completed."""


class Storage:
    def __init__(self, url: str | None = None, token: str | None = None,
                 timeout: float = 8.0, retries: int = 2) -> None:
        self.url = (url or os.getenv("UPSTASH_REDIS_REST_URL", "")).rstrip("/")
        self.token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        self.timeout = max(1.0, float(timeout))
        self.retries = max(0, int(retries))
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
        if self._closed:
            self._closed = False
        if self._client is None and self.configured:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=min(4.0, self.timeout)),
                headers={"Authorization": f"Bearer {self.token}"},
            )

    async def close(self) -> None:
        self._closed = True
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

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
                self._expire_local_locked()
                return self._local.get(key, default)
        try:
            result = await self._request("GET", f"/get/{quote(key, safe='')}")
            return default if result is None else result
        except StorageError:
            log.exception("GET failed for key=%s", key)
            return default

    async def load(self, key: str, default: Any = None) -> Any:
        """Read a JSON-encoded value, returning *default* on missing/corrupt data."""
        value = await self.get(key, None)
        if value is None:
            return default
        if isinstance(value, (dict, list, int, float, bool)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return default
        return default

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if not isinstance(value, str) else value
        if not self.configured:
            async with self._local_lock:
                self._local[key] = encoded
                if ttl is not None:
                    self._local_expiry[key] = time.time() + max(1, int(ttl))
                else:
                    self._local_expiry.pop(key, None)
            return True
        try:
            await self._request("POST", f"/set/{quote(key, safe='')}", content=encoded)
            if ttl is not None:
                await self._request("POST", f"/expire/{quote(key, safe='')}/{max(1, int(ttl))}")
            return True
        except StorageError:
            log.exception("SET failed for key=%s", key)
            return False

    async def save(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Persist a JSON-serializable value through the common storage boundary."""
        try:
            return await self.set(key, value, ttl=ttl)
        except (TypeError, ValueError):
            log.exception("Could not serialize value for key=%s", key)
            return False

    async def setnx(self, key: str, value: str, ttl: int = 15) -> bool:
        ttl = max(1, int(ttl))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked()
                expiry = self._local_expiry.get(key, 0)
                if key in self._local and expiry > time.time():
                    return False
                self._local[key] = value
                self._local_expiry[key] = time.time() + ttl
                return True
        try:
            result = await self._request("POST", f"/set/{quote(key, safe='')}/{quote(value, safe='')}?NX=true&EX={ttl}")
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
                        count += 1; self._local.pop(key, None); self._local_expiry.pop(key, None)
                    self._local_lists.pop(key, None)
                return count
        try:
            return int(await self._request("POST", "/", json=["DEL", *keys]) or 0)
        except StorageError:
            log.exception("DELETE failed for keys=%s", keys)
            return 0

    async def incrby(self, key: str, amount: int) -> int:
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked(); current = int(self._local.get(key, 0) or 0) + int(amount)
                self._local[key] = str(current); return current
        return int(await self._request("POST", f"/incrby/{quote(key, safe='')}/{int(amount)}"))

    async def eval(self, script: str, keys: list[str] | tuple[str, ...] = (), args: list[str] | tuple[str, ...] = ()) -> Any:
        if not self.configured:
            raise StorageError("EVAL requires configured persistent storage")
        return await self._request("POST", "/", json=["EVAL", script, str(len(keys)), *keys, *[str(x) for x in args]])

    async def atomic_transfer(self, sender_key: str, receiver_key: str, amount: int) -> tuple[int, int]:
        amount = int(amount)
        if amount <= 0: raise StorageError("transfer amount must be positive")
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked(); sender = max(0, int(self._local.get(sender_key, 0) or 0)); receiver = max(0, int(self._local.get(receiver_key, 0) or 0))
                if sender < amount: raise StorageError("insufficient balance")
                sender -= amount; receiver += amount; self._local[sender_key] = str(sender); self._local[receiver_key] = str(receiver); return sender, receiver
        script = "local a=tonumber(ARGV[1]); local s=tonumber(redis.call('GET',KEYS[1]) or '0'); if s<a then return {0,-1,-1} end; local ns=s-a; local nr=tonumber(redis.call('GET',KEYS[2]) or '0')+a; redis.call('SET',KEYS[1],ns); redis.call('SET',KEYS[2],nr); return {1,ns,nr}"
        result = await self.eval(script, [sender_key, receiver_key], [str(amount)])
        if not isinstance(result, list) or len(result) != 3 or int(result[0]) != 1: raise StorageError("insufficient balance")
        return int(result[1]), int(result[2])

    async def atomic_claim(self, balance_key: str, marker_key: str, amount: int, ttl: int) -> tuple[bool, int]:
        """Atomically grant a once-per-period reward and record its marker."""
        amount, ttl = int(amount), max(1, int(ttl))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked()
                if marker_key in self._local: return False, int(self._local.get(balance_key, 0) or 0)
                current = int(self._local.get(balance_key, 0) or 0) + amount
                self._local[balance_key] = str(current); self._local[marker_key] = "1"; self._local_expiry[marker_key] = time.time() + ttl
                return True, current
        script = "if redis.call('EXISTS',KEYS[2])==1 then return {0,tonumber(redis.call('GET',KEYS[1]) or '0')} end; redis.call('SET',KEYS[2],'1','EX',ARGV[2]); local n=redis.call('INCRBY',KEYS[1],ARGV[1]); return {1,n}"
        result = await self.eval(script, [balance_key, marker_key], [str(amount), str(ttl)])
        if not isinstance(result, list) or len(result) != 2: raise StorageError("invalid atomic claim response")
        return bool(int(result[0])), int(result[1])

    async def scan(self, pattern: str = "*", count: int = 100) -> list[str]:
        count = max(1, min(int(count), 500))
        if not self.configured:
            async with self._local_lock:
                self._expire_local_locked(); keys = set(self._local) | set(self._local_lists); return sorted(k for k in keys if fnmatch.fnmatchcase(k, pattern))
        found: list[str] = []; cursor = "0"
        try:
            while True:
                result = await self._request("POST", "/", json=["SCAN", cursor, "MATCH", pattern, "COUNT", count])
                if not isinstance(result, list) or len(result) != 2: raise StorageError("invalid SCAN response")
                cursor = str(result[0]); found.extend(str(k) for k in (result[1] or []))
                if cursor == "0": break
            return found
        except StorageError:
            log.exception("SCAN failed for pattern=%s", pattern); return []

    async def lpush(self, key: str, *values: Any) -> int:
        if not values: return 0
        if not self.configured:
            async with self._local_lock:
                items = self._local_lists.setdefault(key, []); [items.insert(0, str(value)) for value in values]; return len(items)
        return int(await self._request("POST", "/", json=["LPUSH", key, *[str(v) for v in values]]) or 0)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        if not self.configured:
            async with self._local_lock:
                items = self._local_lists.get(key, []); return items[start:] if end == -1 else items[start:end + 1]
        return list(await self._request("POST", "/", json=["LRANGE", key, int(start), int(end)]) or [])

    async def exists(self, key: str) -> bool:
        if not self.configured:
            async with self._local_lock: self._expire_local_locked(); return key in self._local or bool(self._local_lists.get(key))
        try: return bool(int(await self._request("GET", f"/exists/{quote(key, safe='')}") or 0))
        except StorageError: return False

    async def ttl(self, key: str) -> int:
        if not self.configured:
            async with self._local_lock:
                expiry = self._local_expiry.get(key)
                if not expiry: return -1
                remaining = int(expiry - time.time())
                if remaining < 0: self._local.pop(key, None); self._local_expiry.pop(key, None); return -2
                return remaining
        try: return int(await self._request("GET", f"/ttl/{quote(key, safe='')}") )
        except StorageError: return -1

    def _expire_local_locked(self) -> None:
        now = time.time()
        for key, expiry in list(self._local_expiry.items()):
            if expiry <= now: self._local.pop(key, None); self._local_expiry.pop(key, None)

    async def _release_lock(self, key: str, token: str) -> None:
        if not self.configured:
            async with self._local_lock:
                if self._local.get(key) == token: self._local.pop(key, None); self._local_expiry.pop(key, None)
            return
        try:
            await self.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end", [key], [token])
        except StorageError: log.warning("Could not release lock %s cleanly; TTL remains the safety net", key)

    @asynccontextmanager
    async def lock(self, name: str, ttl: int = 15, wait: float = 3.0) -> AsyncIterator[bool]:
        key, token = f"lock:{name}", uuid.uuid4().hex; deadline = time.monotonic() + max(0.0, float(wait)); acquired = False
        while time.monotonic() <= deadline:
            if await self.setnx(key, token, ttl): acquired = True; break
            await asyncio.sleep(0.05)
        try: yield acquired
        finally:
            if acquired: await self._release_lock(key, token)


storage = Storage()
