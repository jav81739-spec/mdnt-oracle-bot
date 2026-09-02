"""Concurrency-safe economy primitives for Midnight Oracle."""
from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import quote

from .storage import Storage, StorageError, storage


class EconomyError(RuntimeError):
    """User-visible economy failure that is safe to retry."""


@dataclass(frozen=True)
class Transaction:
    user_id: int
    amount: int
    balance: int
    reason: str


_LOCAL_LOCKS: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def _storage_lock(store: Storage, key: str, ttl: int = 15, wait: float = 5):
    """Acquire a scoped distributed lock without ever deleting another owner's lock."""
    ttl = max(1, int(ttl))
    wait = max(0.0, float(wait))
    if not getattr(store, "configured", False):
        lock = _LOCAL_LOCKS.setdefault(key, asyncio.Lock())
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait)
        except asyncio.TimeoutError:
            yield False
            return
        try:
            yield True
        finally:
            if lock.locked():
                lock.release()
        return

    token = uuid.uuid4().hex
    deadline = time.monotonic() + wait
    acquired = False
    while True:
        try:
            acquired = await store.setnx(f"lock:{key}", token, ttl=ttl)
        except StorageError:
            acquired = False
        if acquired:
            break
        if time.monotonic() >= deadline:
            yield False
            return
        await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    try:
        yield True
    finally:
        release_script = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
        try:
            await store.eval(release_script, [f"lock:{key}"], [token])
        except StorageError:
            # Never fall back to unconditional delete: ownership safety is more important than cleanup.
            pass


# The public Storage.lock surface is installed here so all callers share the same
# ownership-safe implementation without duplicating lock semantics in the storage facade.
if not hasattr(Storage, "lock"):
    Storage.lock = _storage_lock


class EconomyService:
    """Single source of truth for scoped balances and atomic transfers."""
    def __init__(self, store: Storage = storage) -> None:
        self.store = store

    @staticmethod
    def key(user_id: int, scope: int | str | None = None) -> str:
        return f"economy:balance:{scope}:{int(user_id)}" if scope is not None else f"economy:balance:{int(user_id)}"

    async def balance(self, user_id: int, scope: int | str | None = None) -> int:
        key = self.key(user_id, scope)
        try:
            if getattr(self.store, "configured", False):
                # Economy must never interpret a persistent-store outage as a zero balance.
                value = await self.store._request("GET", f"/get/{quote(key, safe='')}")
            else:
                value = await self.store.get(key, "0")
        except StorageError as exc:
            raise EconomyError("persistent economy is temporarily unavailable") from exc
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError) as exc:
            raise EconomyError("economy balance data is invalid") from exc

    async def add(self, user_id: int, amount: int, reason: str = "adjustment", scope: int | str | None = None) -> Transaction:
        amount = int(amount)
        if amount < 0: return await self.remove(user_id, -amount, reason, scope)
        async with self.store.lock(f"economy:{scope}:{int(user_id)}") as acquired:
            if not acquired: raise EconomyError("economy is busy; please retry")
            if amount == 0: return Transaction(int(user_id), 0, await self.balance(user_id, scope), reason)
            try: new_balance = await self.store.incrby(self.key(user_id, scope), amount)
            except StorageError as exc: raise EconomyError("persistent economy is temporarily unavailable") from exc
            return Transaction(int(user_id), amount, max(0, new_balance), reason)

    async def remove(self, user_id: int, amount: int, reason: str = "spend", scope: int | str | None = None) -> Transaction:
        amount = int(amount)
        if amount < 0: return await self.add(user_id, -amount, reason, scope)
        async with self.store.lock(f"economy:{scope}:{int(user_id)}") as acquired:
            if not acquired: raise EconomyError("economy is busy; please retry")
            current = await self.balance(user_id, scope)
            if current < amount: raise EconomyError("insufficient balance")
            if amount == 0: return Transaction(int(user_id), 0, current, reason)
            try: new_balance = await self.store.incrby(self.key(user_id, scope), -amount)
            except StorageError as exc: raise EconomyError("persistent economy is temporarily unavailable") from exc
            if new_balance < 0: raise EconomyError("economy consistency check failed")
            return Transaction(int(user_id), -amount, new_balance, reason)

    async def transfer(self, sender: int, receiver: int, amount: int, reason: str = "transfer", scope: int | str | None = None) -> tuple[Transaction, Transaction]:
        sender, receiver, amount = int(sender), int(receiver), int(amount)
        if sender == receiver: raise EconomyError("cannot transfer to yourself")
        if amount <= 0: raise EconomyError("amount must be positive")
        first, second = sorted((sender, receiver))
        async with self.store.lock(f"economy:{scope}:{first}") as first_lock:
            if not first_lock: raise EconomyError("economy is busy; please retry")
            async with self.store.lock(f"economy:{scope}:{second}") as second_lock:
                if not second_lock: raise EconomyError("economy is busy; please retry")
                try:
                    sender_balance, receiver_balance = await self.store.atomic_transfer(self.key(sender, scope), self.key(receiver, scope), amount)
                except StorageError as exc:
                    if "insufficient" in str(exc).lower(): raise EconomyError("insufficient balance") from exc
                    raise EconomyError("persistent economy is temporarily unavailable") from exc
                return Transaction(sender, -amount, sender_balance, reason), Transaction(receiver, amount, receiver_balance, reason)

    async def claim_once(self, user_id: int, amount: int, marker: str, ttl: int, reason: str, scope: int | str | None = None) -> Transaction:
        """Grant a reward and record its claim marker in one atomic operation."""
        try:
            claimed, balance = await self.store.atomic_claim(self.key(user_id, scope), f"economy:claim:{scope}:{int(user_id)}:{marker}", int(amount), ttl)
        except StorageError as exc:
            raise EconomyError("persistent economy is temporarily unavailable") from exc
        return Transaction(int(user_id), int(amount) if claimed else 0, balance, reason)


service = EconomyService()
