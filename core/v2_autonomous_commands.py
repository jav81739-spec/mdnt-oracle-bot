"""Compatibility shim for the renamed Oracle Instinct command surface."""
from .oracle_instinct_commands import register, settrigger, triggerinfo

# Compatibility contract: the runtime still reads this established storage namespace.
KEY_PREFIX = "v2:autonomous:trigger:"

__all__ = ["register", "settrigger", "triggerinfo", "KEY_PREFIX"]
