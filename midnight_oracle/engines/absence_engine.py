"""Quiet-member recognition with non-needy absence pings."""
from __future__ import annotations
from dataclasses import dataclass
from ..database import Database, now_ts

@dataclass(slots=True)
class AbsenceCandidate:
    """Describe a regular member eligible for one gentle absence check."""
    user_id: int; group_id: int; name: str; tier: str; last_active: float

class AbsenceEngine:
    """Detect established members who have been absent without pestering them."""
    def __init__(self, db: Database) -> None:
        """Bind the absence engine to SQLite."""
        self.db=db
    async def check_group(self, group_id: int) -> list[AbsenceCandidate]:
        """Return regular-or-better members absent five days and unpinged for fourteen days."""
        cutoff=now_ts()-5*86400; pingcut=now_ts()-14*86400
        rows=await self.db.fetchall("SELECT user_id,preferred_name,relationship_tier,last_seen FROM members WHERE group_id=? AND interaction_count>=10 AND last_seen<? AND relationship_tier IN ('regular','known','close') AND user_id NOT IN (SELECT user_id FROM absence_log WHERE group_id=? AND pinged_at>?)",(group_id,cutoff,group_id,pingcut))
        return [AbsenceCandidate(int(r[0]),group_id,str(r[1] or 'friend'),str(r[2]),float(r[3])) for r in rows]
    async def generate_ping(self, member: AbsenceCandidate, group_id: int) -> str:
        """Create a tier-calibrated, non-guilt-tripping absence message."""
        if member.tier=='close': return f"Haven't heard you in a while, {member.name}. Everything good? 🌙"
        if member.tier=='known': return f"Haven't heard you in a while, {member.name}. Hope the offline world is treating you well."
        return f"{member.name} has been quiet. Hope the offline world is treating you well."
    async def record_ping(self, member: AbsenceCandidate, response: str='') -> None:
        """Record an absence ping so it cannot repeat within the configured window."""
        await self.db.execute("INSERT INTO absence_log(user_id,group_id,last_active,pinged_at,ping_response) VALUES(?,?,?,?,?)",(member.user_id,member.group_id,member.last_active,now_ts(),response[:500]))
