"""Compatibility shim for the renamed Oracle Instinct command surface."""
from .oracle_instinct_commands import register, settrigger, triggerinfo

__all__ = ["register", "settrigger", "triggerinfo"]
