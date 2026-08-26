"""Concurrency-safe economy primitives for Midnight Oracle."""
from __future__ import annotations

from dataclasses import dataclass

from .storage import Storage, storage


class EconomyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Transaction:
    user_id: int
    amount: int
    balance: int
    reason: str


class EconomyService:
    """Single source of truth for balances.

    Balances live in individual keys rather than one giant JSON blob. Mutations
    use atomic INCRBY plus a short-lived lock, eliminating the legacy GET ->
    calculate -> SET lost-update pattern.
    """
    def __init__(self, store: Storage = storage) -> None:
        self.store = store

    @staticmethod
    def key(user_id: int) -> str:
        return f"economy:balance:{int(user_id)}"

    async def balance(self, user_id: int) -> int:
        value = await self.store.get(self.key(user_id), "0")
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    async def add(self, user_id: int, amount: int, reason: str = "adjustment") -> Transaction:
        if amount < 0:
            return await self.remove(user_id, -amount, reason)
        if amount == 0:
            return Transaction(user_id, 0, await self.balance(user_id), reason)
        async with self.store.lock(f"economy:{user_id}") as acquired:
            if not acquired:
                raise EconomyError("economy is busy; please retry")
            new_balance = await self.store.incrby(self.key(user_id), amount)
            if new_balance < 0:
                await self.store.incrby(self.key(user_id), -new_balance)
                new_balance = 0
            return Transaction(user_id, amount, new_balance, reason)

    async def remove(self, user_id: int, amount: int, reason: str = "spend") -> Transaction:
        if amount < 0:
            return await self.add(user_id, -amount, reason)
        if amount == 0:
            return Transaction(user_id, 0, await self.balance(user_id), reason)
        async with self.store.lock(f"economy:{user_id}") as acquired:
            if not acquired:
                raise EconomyError("economy is busy; please retry")
            current = await self.balance(user_id)
            if current < amount:
                raise EconomyError("insufficient balance")
            new_balance = await self.store.incrby(self.key(user_id), -amount)
            return Transaction(user_id, -amount, new_balance, reason)

    async def transfer(self, sender: int, receiver: int, amount: int, reason: str = "transfer") -> tuple[Transaction, Transaction]:
        if sender == receiver:
            raise EconomyError("cannot transfer to yourself")
        if amount <= 0:
            raise EconomyError("amount must be positive")
        first, second = sorted((int(sender), int(receiver)))
        async with self.store.lock(f"economy:{first}") as first_lock:
            if not first_lock:
                raise EconomyError("economy is busy; please retry")
            async with self.store.lock(f"economy:{second}") as second_lock:
                if not second_lock:
                    raise EconomyError("economy is busy; please retry")
                balance = await self.balance(sender)
                if balance < amount:
                    raise EconomyError("insufficient balance")
                await self.store.incrby(self.key(sender), -amount)
                receiver_balance = await self.store.incrby(self.key(receiver), amount)
                return (
                    Transaction(sender, -amount, balance - amount, reason),
                    Transaction(receiver, amount, receiver_balance, reason),
                )


service = EconomyService()
