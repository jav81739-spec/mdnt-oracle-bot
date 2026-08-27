"""Midnight Oracle core engine."""

from .economy import EconomyError, EconomyService, Transaction, service as economy
from .storage import Storage, StorageError, storage

# Install the polling-lease namespace before bot.py imports Storage. This keeps
# one poller per bot token while allowing a freshly rotated token to start
# immediately instead of inheriting an old token's Redis lease.
from . import polling_lease_namespace as _polling_lease_namespace  # noqa: F401,E402

# Every Telegram Application created by the production runtime gets a single
# safe error sink. This prevents python-telegram-bot from falling back to
# "No error handlers are registered" and lets one bad update be logged without
# taking down the polling process.
from .error_handling import install_error_handler as _install_error_handler  # noqa: E402

try:
    from telegram.ext import Application as _TelegramApplication
    _original_application_init = _TelegramApplication.__init__

    def _midnight_application_init(self, *args, **kwargs):
        _original_application_init(self, *args, **kwargs)
        _install_error_handler(self)

    if not getattr(_TelegramApplication, "_midnight_error_handler_patched", False):
        _TelegramApplication.__init__ = _midnight_application_init
        _TelegramApplication._midnight_error_handler_patched = True
except Exception:
    # Import-time hardening must never prevent the bot from starting.
    pass

__all__ = ["Storage", "StorageError", "storage", "EconomyService", "EconomyError", "Transaction", "economy"]
