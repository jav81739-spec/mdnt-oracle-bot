"""Explicit-only sticker policy for Midnight Oracle.

Incoming stickers are user content, not invitations for the bot to answer. Automatic
sticker-to-sticker replies were a major source of noisy, unsolicited output, so the
canonical runtime deliberately keeps this surface inert. Explicit /sticker requests
are handled by the command surface instead.
"""
from __future__ import annotations

import logging

log = logging.getLogger("midnight.stickers")


async def sticker_to_sticker(update, context) -> None:
    """Never answer an incoming sticker automatically."""
    del update, context
    return


def install(application) -> None:
    """Keep the compatibility installation hook without registering a spam handler."""
    del application
    log.info("STICKER_AUTOREPLY_DISABLED | mode=explicit_only")
