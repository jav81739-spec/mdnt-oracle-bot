"""Privacy-safe secret events with complete teaser/reveal lifecycle."""
from __future__ import annotations
from dataclasses import dataclass
from ..database import Database, now_ts
from telegram.error import BadRequest

@dataclass(slots=True)
class SecretEvent:
    """Represent a persisted teaser/reveal event."""
    group_id: int
    event_type: str
    content: str

class SecretEventEngine:
    """Generate, persist, reveal, and recover rare secret events."""
    def __init__(self, db: Database) -> None:
        """Bind the engine to SQLite."""
        self.db = db

    async def evaluate(self, group_id: int) -> SecretEvent | None:
        """Return a rare aggregate event when the group qualifies."""
        recent = await self.db.fetchone('SELECT COUNT(*) FROM secret_events_log WHERE group_id=? AND sent_at>?', (group_id, now_ts()-604800))
        if recent and int(recent[0]) >= 2:
            return None
        signals = await self.db.fetchone('SELECT COUNT(*) FROM mood_log WHERE group_id=? AND timestamp>?', (group_id, now_ts()-86400))
        if not signals or int(signals[0]) < 8:
            return None
        return SecretEvent(group_id, 'activity_stat', f'Oracle noticed {int(signals[0])} mood signals in this room today. The room has been busy.')

    async def format_event(self, event: SecretEvent) -> tuple[str, str]:
        """Return teaser and full reveal text."""
        return '☾ Oracle has noticed something.', f'☾ Oracle noticed:\n\n{event.content}\n\n— observed quietly 🌙'

    async def record(self, event: SecretEvent, message_id: int | None = None) -> int:
        """Persist a sent event and return its database id."""
        cur = await self.db.db.execute('INSERT INTO secret_events_log(group_id,event_type,content,sent_at,teaser_message_id) VALUES(?,?,?,?,?)', (event.group_id, event.event_type, event.content, now_ts(), message_id))
        await self.db.db.commit()
        return int(cur.lastrowid)

    async def get(self, event_id: int):
        """Fetch a complete secret event row."""
        return await self.db.get_secret_event(event_id)

    async def reveal(self, event_id: int, bot, message_id: int | None = None, by_user_id: int | None = None, group_id: int | None = None) -> bool:
        """Reveal an event exactly once, editing the teaser or replacing a deleted message."""
        row = await self.db.get_secret_event(event_id)
        if not row or row['revealed_at']:
            return False
        gid = int(group_id if group_id is not None else row['group_id'])
        mid = int(message_id if message_id is not None else (row['teaser_message_id'] or 0))
        text = f'☾ Oracle noticed:\n\n{row["content"]}\n\n— observed quietly 🌙'
        try:
            if mid:
                await bot.edit_message_text(text, chat_id=gid, message_id=mid)
            else:
                sent = await bot.send_message(gid, text)
                mid = sent.message_id
        except BadRequest:
            try:
                sent = await bot.send_message(gid, text)
                mid = sent.message_id
            except Exception:
                return False
        except Exception:
            return False
        if await self.db.mark_revealed(event_id, by_user_id, mid):
            return True
        return False

    async def recover_unrevealed(self, bot) -> None:
        """Reveal overdue unrevealed events after a restart."""
        rows = await self.db.fetchall('SELECT id,group_id,teaser_message_id,sent_at FROM secret_events_log WHERE revealed_at IS NULL AND sent_at<?', (now_ts()-1800,))
        for row in rows:
            try:
                await self.reveal(int(row['id']), bot, int(row['teaser_message_id'] or 0), None, int(row['group_id']))
            except Exception:
                continue
