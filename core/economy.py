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
async def _storage_lock(store: Storage, key: str, ttl: int = 60, wait: float = 5):
    """Acquire a scoped distributed lock without deleting another owner's lock."""
    ttl = max(1, int(ttl)); wait = max(0.0, float(wait))
    if not getattr(store, "configured", False):
        lock = _LOCAL_LOCKS.setdefault(key, asyncio.Lock())
        try: await asyncio.wait_for(lock.acquire(), timeout=wait)
        except asyncio.TimeoutError: yield False; return
        try: yield True
        finally:
            if lock.locked(): lock.release()
        return
    token = uuid.uuid4().hex; deadline = time.monotonic() + wait
    while True:
        try: acquired = await store.setnx(f"lock:{key}", token, ttl=ttl)
        except StorageError: acquired = False
        if acquired: break
        if time.monotonic() >= deadline: yield False; return
        await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    try: yield True
    finally:
        script = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
        try: await store.eval(script, [f"lock:{key}"], [token])
        except StorageError: pass


if not hasattr(Storage, "lock"):
    Storage.lock = _storage_lock


class EconomyService:
    """Single source of truth for scoped balances and atomic transfers."""
    def __init__(self, store: Storage = storage) -> None: self.store = store

    @staticmethod
    def key(user_id: int, scope: int | str | None = None) -> str:
        return f"economy:balance:{scope}:{int(user_id)}" if scope is not None else f"economy:balance:{int(user_id)}"

    async def balance(self, user_id: int, scope: int | str | None = None) -> int:
        key = self.key(user_id, scope)
        try:
            value = await self.store._request("GET", f"/get/{quote(key, safe='')}") if getattr(self.store, "configured", False) else await self.store.get(key, "0")
        except StorageError as exc: raise EconomyError("persistent economy is temporarily unavailable") from exc
        try: return max(0, int(value or 0))
        except (TypeError, ValueError) as exc: raise EconomyError("economy balance data is invalid") from exc

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
            if amount == 0: return Transaction(int(user_id), 0, await self.balance(user_id, scope), reason)
            try: new_balance = await self.store.atomic_remove(self.key(user_id, scope), amount)
            except StorageError as exc:
                if "insufficient" in str(exc).lower(): raise EconomyError("insufficient balance") from exc
                raise EconomyError("persistent economy is temporarily unavailable") from exc
            return Transaction(int(user_id), -amount, new_balance, reason)

    async def _idempotent_mutation(self, user_id: int, amount: int, marker: str, ttl: int, reason: str, scope: int | str | None, *, debit: bool) -> Transaction:
        """Apply a balance mutation exactly once for a durable operation marker."""
        amount = int(amount)
        if amount < 0: return await self._idempotent_mutation(user_id, -amount, marker, ttl, reason, scope, debit=not debit)
        if amount == 0: return Transaction(int(user_id), 0, await self.balance(user_id, scope), reason)
        balance_key = self.key(user_id, scope); marker_key = f"economy:op:{scope}:{int(user_id)}:{marker}"
        script = """
local done=redis.call('GET',KEYS[2]); local current=tonumber(redis.call('GET',KEYS[1]) or '0')
if done then return {0,current,1} end
local amount=tonumber(ARGV[1]); if ARGV[3]=='debit' and current<amount then return {-1,current,0} end
local next=current+amount; if ARGV[3]=='debit' then next=current-amount end
redis.call('SET',KEYS[1],next); redis.call('SET',KEYS[2],'1','EX',ARGV[2]); return {1,next,0}
"""
        try: result = await self.store.eval(script, [balance_key, marker_key], [str(amount), str(max(1, int(ttl))), "debit" if debit else "credit"])
        except StorageError as exc: raise EconomyError("persistent economy is temporarily unavailable") from exc
        if not isinstance(result, (list, tuple)) or len(result) < 3: raise EconomyError("economy consistency check failed")
        status, balance, _ = map(int, result[:3])
        if status < 0: raise EconomyError("insufficient balance")
        return Transaction(int(user_id), 0 if status == 0 else (-amount if debit else amount), max(0, balance), reason)

    async def add_once(self, user_id: int, amount: int, marker: str, ttl: int = 604800, reason: str = "adjustment", scope: int | str | None = None) -> Transaction:
        return await self._idempotent_mutation(user_id, amount, marker, ttl, reason, scope, debit=False)

    async def remove_once(self, user_id: int, amount: int, marker: str, ttl: int = 604800, reason: str = "spend", scope: int | str | None = None) -> Transaction:
        return await self._idempotent_mutation(user_id, amount, marker, ttl, reason, scope, debit=True)

    async def transfer(self, sender: int, receiver: int, amount: int, reason: str = "transfer", scope: int | str | None = None) -> tuple[Transaction, Transaction]:
        sender, receiver, amount = int(sender), int(receiver), int(amount)
        if sender == receiver: raise EconomyError("cannot transfer to yourself")
        if amount <= 0: raise EconomyError("amount must be positive")
        first, second = sorted((sender, receiver))
        async with self.store.lock(f"economy:{scope}:{first}") as first_lock:
            if not first_lock: raise EconomyError("economy is busy; please retry")
            async with self.store.lock(f"economy:{scope}:{second}") as second_lock:
                if not second_lock: raise EconomyError("economy is busy; please retry")
                try: sender_balance, receiver_balance = await self.store.atomic_transfer(self.key(sender, scope), self.key(receiver, scope), amount)
                except StorageError as exc:
                    if "insufficient" in str(exc).lower(): raise EconomyError("insufficient balance") from exc
                    raise EconomyError("persistent economy is temporarily unavailable") from exc
                return Transaction(sender,-amount,sender_balance,reason), Transaction(receiver,amount,receiver_balance,reason)

    async def claim_once(self, user_id: int, amount: int, marker: str, ttl: int, reason: str, scope: int | str | None = None) -> Transaction:
        try: claimed, balance = await self.store.atomic_claim(self.key(user_id, scope), f"economy:claim:{scope}:{int(user_id)}:{marker}", int(amount), ttl)
        except StorageError as exc: raise EconomyError("persistent economy is temporarily unavailable") from exc
        return Transaction(int(user_id), int(amount) if claimed else 0, balance, reason)


service = EconomyService()
