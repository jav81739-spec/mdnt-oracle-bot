"""Persistent, cancellable game state machine."""
from __future__ import annotations
import json
from abc import ABC
from ..database import Database, now_ts

class BaseGame(ABC):
    """Base contract shared by every group game."""
    game_type='base'; min_players=2
    def __init__(self,db:Database)->None:
        """Bind the game to SQLite."""; self.db=db
    async def start(self,group_id:int,starter:object)->str:
        """Create an active session and return its opening message."""
        row=await self.db.fetchone("SELECT id FROM game_sessions WHERE group_id=? AND is_active=1",(group_id,))
        if row: return '☾ A game is already awake here. Finish that one first.'
        await self.db.execute("INSERT INTO game_sessions(group_id,game_type,state,current_turn_user_id,started_at,is_active) VALUES(?,?,?,?,?,1)",(group_id,self.game_type,json.dumps({'players':[int(getattr(starter,'user_id',0))]}),int(getattr(starter,'user_id',0)),now_ts()))
        return f"☾ {self.game_type.replace('_',' ').title()}\nStarted by {getattr(starter,'preferred_name',None) or getattr(starter,'first_name','friend')}. Join when you're ready."
    async def get_state(self,group_id:int)->dict:
        """Return the active serialized state or an empty state."""
        row=await self.db.fetchone("SELECT state FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1 ORDER BY id DESC LIMIT 1",(group_id,self.game_type)); return json.loads(row[0]) if row else {}
    async def handle_action(self,action:str,member:object)->str:
        """Process a generic game action without crashing."""; return f"☾ {action} noted."
    async def end(self,group_id:int)->str:
        """Gracefully close the active session and record its summary."""
        row=await self.db.fetchone("SELECT id,state FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1 ORDER BY id DESC LIMIT 1",(group_id,self.game_type))
        if not row:return '☾ No active game.'
        await self.db.execute("UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=?",(now_ts(),int(row[0])))
        await self.db.execute("INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)",(group_id,self.game_type,None,'Ended by group/admin.',now_ts()))
        return '☾ Game closed. No hard feelings.'

class GameEngine:
    """Route game sessions while keeping one active game per group."""
    def __init__(self,db:Database)->None:
        """Bind the game coordinator to SQLite."""; self.db=db
    async def endgame(self,group_id:int)->str:
        """End the active game in a group, regardless of game type."""
        row=await self.db.fetchone("SELECT id,game_type FROM game_sessions WHERE group_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",(group_id,))
        if not row:return '☾ No active game.'
        await self.db.execute("UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=?",(now_ts(),int(row[0])))
        await self.db.execute("INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)",(group_id,str(row[1]),None,'Ended gracefully.',now_ts())); return '☾ The game is over. The room survives.'
