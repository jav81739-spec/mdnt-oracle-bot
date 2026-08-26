"""Concurrency-safe economy primitives for Midnight Oracle."""
from __future__ import annotations

from dataclasses import dataclass

from .storage import Storage, StorageError, storage


class EconomyError(RuntimeError):
    """User-visible economy failure that is safe to retry."""


@dataclass(frozen=True)
class Transaction:
    user_id: int
    amount: int
    balance: int
    reason: str


class EconomyService:
    """Single source of truth for scoped balances and atomic transfers."""
    def __init__(self, store: Storage = storage) -> None:
        self.store = store

    @staticmethod
    def key(user_id: int, scope: int | str | None = None) -> str:
        return f"economy:balance:{scope}:{int(user_id)}" if scope is not None else f"economy:balance:{int(user_id)}"

    async def balance(self, user_id: int, scope: int | str | None = None) -> int:
        value = await self.store.get(self.key(user_id, scope), "0")
        try: return max(0, int(value or 0))
        except (TypeError, ValueError): return 0

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
