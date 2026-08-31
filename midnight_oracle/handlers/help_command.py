"""Reliable compatibility bridge for the canonical premium member command archive."""
from __future__ import annotations

from telegram import MessageEntity, Update
from telegram.ext import ContextTypes
from handlers.help_command import _build_archive, _live_member_commands

_MAX_CHUNK = 3800


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _chunks(text: str, entities: list[MessageEntity]):
    """Split the archive on line boundaries and preserve command entities."""
    lines = text.splitlines(keepends=True)
    chunks: list[tuple[str, list[MessageEntity]]] = []
    current = ""
    current_start = 0

    for line in lines:
        if current and len(current) + len(line) > _MAX_CHUNK:
            chunks.append((current, _entities_for_range(entities, current_start, current)))
            current_start += len(current)
            current = ""
        current += line

    if current:
        chunks.append((current.rstrip("\n"), _entities_for_range(entities, current_start, current)))
    return chunks


def _entities_for_range(entities: list[MessageEntity], start: int, value: str) -> list[MessageEntity]:
    end = start + len(value)
    result: list[MessageEntity] = []
    for entity in entities:
        entity_start = entity.offset
        entity_end = entity.offset + entity.length
        if entity_start >= start and entity_end <= end:
            raw_prefix = value[:entity_start - start]
            result.append(MessageEntity(type=entity.type, offset=_utf16_len(raw_prefix), length=entity.length))
    return result


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the complete help archive without exceeding Telegram's 4096-char limit."""
    message = update.effective_message
    if not message:
        return
    live = _live_member_commands(context.application)
    text, entities = _build_archive(live)
    chunks = _chunks(text, entities)
    for index, (chunk, chunk_entities) in enumerate(chunks):
        try:
            await message.reply_text(
                chunk,
                entities=chunk_entities,
                disable_web_page_preview=True,
                reply_to_message_id=message.message_id if index == 0 else None,
            )
        except Exception:
            # Never lose the Help command because entity metadata is rejected.
            await message.reply_text(
                chunk,
                disable_web_page_preview=True,
                reply_to_message_id=message.message_id if index == 0 else None,
            )


__all__ = ["help_command"]
