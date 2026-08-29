"""Five-round word scramble game."""
from __future__ import annotations
import random
from .game_engine import BaseGame

WORDS=('midnight','oracle','coffee','moonlight','friendship','cricket','silence','mystique','thunder','lantern')
class WordScrambleGame(BaseGame):
    """Run a five-round deterministic-state word scramble."""
    game_type='word_scramble'
    async def start(self,group_id:int,starter:object)->str:
        """Open a five-round scramble session."""
        word=random.choice(WORDS); state={'word':word,'round':1,'scores':{}}; await super().start(group_id,starter)
        row=await self.db.fetchone("SELECT id FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1",(group_id,self.game_type));
        if row: await self.db.execute("UPDATE game_sessions SET state=? WHERE id=?",(__import__('json').dumps(state),int(row[0])))
        return '☾ Word Scramble — round 1\n'+''.join(random.sample(word,len(word)))
    async def handle_action(self,action:str,member:object)->str:
        """Accept a guess and award a correct first answer."""
        state=await self.get_state(int(getattr(member,'group_id',0)))
        if not state:return '☾ No scramble is active.'
        if action.casefold()==str(state.get('word','')).casefold(): return f"☾ Correct, {getattr(member,'preferred_name','friend')}."
        return '☾ Not quite.'
