"""Rolling group personality learning."""
from __future__ import annotations
import json
from dataclasses import dataclass
from ..database import Database, now_ts

@dataclass(slots=True)
class GroupProfile:
    """Snapshot of group social character."""
    humour_level:float; depth_level:float; activity_pattern:str; favourite_topics:list[str]; quiet_periods:list[str]; peak_hours:list[int]

class GroupIdentityEngine:
    """Learn aggregate group behaviour without cross-group member data."""
    def __init__(self,db:Database)->None:
        """Bind identity learning to SQLite."""; self.db=db
    async def update(self,group_id:int,message:object,mood:object)->None:
        """Update rolling humour/depth/activity signals from one message."""
        text=str(getattr(message,'text',None) or message or '').lower(); humour=float(getattr(mood,'humour',.5)); deep=1.0 if any(x in text for x in ('why','meaning','life','miss','feel','kyun','zindagi')) else 0.0
        row=await self.db.fetchone("SELECT humour_level,depth_level FROM group_identity WHERE group_id=?",(group_id,))
        if row: h=.9*float(row[0])+.1*humour; d=.9*float(row[1])+.1*deep; await self.db.execute("UPDATE group_identity SET humour_level=?,depth_level=?,last_updated=? WHERE group_id=?",(h,d,now_ts(),group_id))
        else: await self.db.execute("INSERT INTO group_identity(group_id,humour_level,depth_level,last_updated) VALUES(?,?,?,?)",(group_id,humour,deep,now_ts()))
    async def get_profile(self,group_id:int)->GroupProfile:
        """Return a current aggregate profile."""
        row=await self.db.fetchone("SELECT humour_level,depth_level,activity_pattern,favourite_topics,quiet_periods,peak_hours FROM group_identity WHERE group_id=?",(group_id,))
        if not row:return GroupProfile(.5,.5,'scattered',[],[],[])
        return GroupProfile(float(row[0]),float(row[1]),str(row[2]),json.loads(row[3] or '[]'),json.loads(row[4] or '[]'),json.loads(row[5] or '[]'))
    async def generate_group_line(self,group_id:int)->str:
        """Return one restrained observation about group character."""
        p=await self.get_profile(group_id); return '☾ The room feels unusually quiet tonight.' if p.humour_level<.35 else '☾ The room has a little chaos in it tonight.'
