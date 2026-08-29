"""Would You Rather game using Telegram-friendly vote state."""
from __future__ import annotations
import json
from .game_engine import BaseGame
from ..database import now_ts

class WouldYouRatherGame(BaseGame):
    """Persist a dilemma and vote counts for a group."""
    game_type='would_you_rather'
    async def start(self,group_id:int,starter:object)->str:
        """Start a dilemma round."""
        return await super().start(group_id,starter)+'\nA or B? Vote honestly. Poll closes after 60 seconds.'
    async def handle_action(self,action:str,member:object)->str:
        """Record a vote once per member."""
        row=await self.db.fetchone("SELECT id,state FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1",(int(getattr(member,'group_id',0)),self.game_type))
        if not row:return '☾ No WYR is active.'
        state=json.loads(row[1]); votes=state.setdefault('votes',{}); uid=str(getattr(member,'user_id',0));
        if uid in votes:return '☾ One vote is enough.'
        votes[uid]=action; await self.db.execute("UPDATE game_sessions SET state=? WHERE id=?",(json.dumps(state),int(row[0]))); return '☾ Counted.'
