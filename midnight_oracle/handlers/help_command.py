"""Compatibility bridge to the canonical interactive Help command hall."""
from __future__ import annotations

from handlers.help_command import help_callback as _canonical_help_callback
from handlers.help_command import help_command as _canonical_help_command


async def help_command(update, context):
    """Use the canonical interactive Help UI; never emit the legacy archive."""
    return await _canonical_help_command(update, context)


async def help_callback(update, context):
    """Handle Help section callbacks from the canonical UI."""
    return await _canonical_help_callback(update, context)


__all__ = ["help_command", "help_callback"]
