"""Midnight Oracle core engine."""

from .economy import EconomyError, EconomyService, Transaction, service as economy
from .storage import Storage, StorageError, storage

# Install the polling-lease namespace before bot.py imports Storage. This keeps
# one poller per bot token while allowing a freshly rotated token to start
# immediately instead of inheriting an old token's Redis lease.
from . import polling_lease_namespace as _polling_lease_namespace  # noqa: F401,E402

__all__ = ["Storage", "StorageError", "storage", "EconomyService", "EconomyError", "Transaction", "economy"]
