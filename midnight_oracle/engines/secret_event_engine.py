"""Rare, privacy-safe group observations."""
from __future__ import annotations
from dataclasses import dataclass
from ..database import Database, now_ts

@dataclass(slots=True)
class SecretEvent:
    """Represent a teaser/reveal pair backed only by public aggregate signals."""
    group_id:int; event_type:str; content:str

class SecretEventEngine:
    """Generate at most two safe secret observations per week."""
    def __init__(self,db:Database)->None:
        """Bind the engine to SQLite."""; self.db=db
    async def evaluate(self,group_id:int)->SecretEvent|None:
        """Return a rare aggregate event when the group has earned one."""
        row=await self.db.fetchone("SELECT COUNT(*) FROM secret_events_log WHERE group_id=? AND sent_at>?",(group_id,now_ts()-7*86400))
        if row and int(row[0])>=2:return None
        row=await self.db.fetchone("SELECT COUNT(*) FROM mood_log WHERE group_id=? AND timestamp>?",(group_id,now_ts()-86400))
        if not row or int(row[0])<8:return None
        msg=f"Oracle has noticed the room had {int(row[0])} mood signals today. The room has been busy."
        return SecretEvent(group_id,'activity_stat',msg)
    async def format_event(self,event:SecretEvent)->tuple[str,str]:
        """Format a privacy-safe teaser and reveal."""
        return ('☾ Oracle has noticed something.','👁 '+event.content)
    async def record(self,event:SecretEvent)->None:
        """Record a sent secret event."""; await self.db.execute("INSERT INTO secret_events_log(group_id,event_type,content,sent_at) VALUES(?,?,?,?)",(event.group_id,event.event_type,event.content,now_ts()))
