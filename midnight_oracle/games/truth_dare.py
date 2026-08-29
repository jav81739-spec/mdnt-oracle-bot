"""Truth or Dare group game."""
from __future__ import annotations
import random
from .game_engine import BaseGame

class TruthDareGame(BaseGame):
    """Run a lightweight five-round Truth or Dare session."""
    game_type='truth_dare'
    async def start(self,group_id:int,starter:object)->str:
        """Start Truth or Dare with inline action labels."""
        text=await super().start(group_id,starter); return text+'\n[Truth 🃏] [Dare 🎯] [Pass 🙈]'
    async def handle_action(self,action:str,member:object)->str:
        """Process Truth, Dare, Pass, or join actions."""
        state=await self.get_state(int(getattr(member,'group_id',0))); uid=int(getattr(member,'user_id',0)); players=set(state.get('players',[])); players.add(uid)
        if state:
            state['players']=list(players); state['rounds']=int(state.get('rounds',0))+1
            row=await self.db.fetchone("SELECT id FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1",(member.group_id,self.game_type))
            if row: await self.db.execute("UPDATE game_sessions SET state=? WHERE id=?",(__import__('json').dumps(state),int(row[0])))
        return {'truth':'☾ Truth: what is something you pretend not to care about?','dare':'☾ Dare: send the next message using only three words.','pass':'☾ Passed. Oracle judges nothing.'}.get(action,'☾ Choose Truth, Dare, or Pass.')
