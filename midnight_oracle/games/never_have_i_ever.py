"""Never Have I Ever game state."""
from __future__ import annotations
import json
from .game_engine import BaseGame

class NeverHaveIEverGame(BaseGame):
    """Run progressively deeper but safe group statements."""
    game_type='never_have_i_ever'
    async def start(self,group_id:int,starter:object)->str:
        """Open the first NHIE round."""; return await super().start(group_id,starter)+'\n[I have 🙋] [Never 🙅]'
    async def handle_action(self,action:str,member:object)->str:
        """Record one member's current answer."""
        row=await self.db.fetchone("SELECT id,state FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1",(int(getattr(member,'group_id',0)),self.game_type))
        if not row:return '☾ No NHIE game is active.'
        state=json.loads(row[1]); answers=state.setdefault('answers',{}); answers[str(getattr(member,'user_id',0))]=action
        await self.db.execute("UPDATE game_sessions SET state=? WHERE id=?",(json.dumps(state),int(row[0]))); return '☾ Noted. Oracle is not judging. 👁'
