"""Async SQLite persistence for Midnight Oracle."""
from __future__ import annotations
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="""
CREATE TABLE IF NOT EXISTS members (user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, username TEXT DEFAULT '', preferred_name TEXT DEFAULT '', relationship_tier TEXT DEFAULT 'new', interaction_count INTEGER DEFAULT 0, last_seen REAL DEFAULT 0, interaction_preference TEXT DEFAULT 'lurker', created_at REAL NOT NULL, PRIMARY KEY(user_id, group_id));
CREATE TABLE IF NOT EXISTS member_memory (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,group_id INTEGER NOT NULL,memory_type TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS group_profile (group_id INTEGER PRIMARY KEY,group_name TEXT DEFAULT '',timezone TEXT NOT NULL,active_hours_start INTEGER DEFAULT 8,active_hours_end INTEGER DEFAULT 23,humour_level REAL DEFAULT .5,morning_active INTEGER DEFAULT 1,evening_active INTEGER DEFAULT 1,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cooldowns (id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT NOT NULL,scope_id TEXT NOT NULL,cooldown_type TEXT NOT NULL,expires_at REAL NOT NULL,UNIQUE(scope,scope_id,cooldown_type));
CREATE TABLE IF NOT EXISTS mood_log (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,group_id INTEGER NOT NULL,energy REAL NOT NULL,humour REAL NOT NULL,social REAL NOT NULL,stress REAL NOT NULL,playful REAL NOT NULL,timestamp REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oracle_moments_log (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,moment_type TEXT NOT NULL,content TEXT NOT NULL,sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS scheduled_log (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,schedule_type TEXT NOT NULL,sent_at REAL NOT NULL,had_interaction INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS inside_jokes (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,joke_text TEXT NOT NULL,origin_message TEXT NOT NULL,first_seen REAL NOT NULL,last_referenced REAL NOT NULL,reference_count INTEGER DEFAULT 1,members_involved TEXT DEFAULT '',first_day INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,group_id INTEGER NOT NULL,achievement_key TEXT NOT NULL,achieved_at REAL NOT NULL,is_secret INTEGER DEFAULT 0,is_revealed INTEGER DEFAULT 0,UNIQUE(user_id,group_id,achievement_key));
CREATE TABLE IF NOT EXISTS absence_log (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,group_id INTEGER NOT NULL,last_active REAL NOT NULL,pinged_at REAL,ping_response TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sticker_events (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,trigger_context TEXT NOT NULL,sticker_id TEXT,sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS game_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,game_type TEXT NOT NULL,state TEXT NOT NULL,current_turn_user_id INTEGER,started_at REAL NOT NULL,ended_at REAL,is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS game_history (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,game_type TEXT NOT NULL,winner_user_id INTEGER,summary TEXT DEFAULT '',played_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,predictor_user_id INTEGER NOT NULL,prediction_text TEXT NOT NULL,reveal_date REAL NOT NULL,actual_outcome TEXT DEFAULT '',created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS group_identity (group_id INTEGER PRIMARY KEY,humour_level REAL DEFAULT .5,depth_level REAL DEFAULT .5,activity_pattern TEXT DEFAULT 'scattered',favourite_topics TEXT DEFAULT '[]',quiet_periods TEXT DEFAULT '[]',peak_hours TEXT DEFAULT '[]',last_updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS secret_events_log (id INTEGER PRIMARY KEY AUTOINCREMENT,group_id INTEGER NOT NULL,event_type TEXT NOT NULL,content TEXT NOT NULL,sent_at REAL NOT NULL);
"""

def now_ts()->float:
    """Return current UTC Unix timestamp."""; return datetime.now(timezone.utc).timestamp()

class Database:
    """Own one async SQLite connection and its persistence operations."""
    def __init__(self,path:str)->None:
        """Create a database manager."""; self.path=str(Path(path));self._db:aiosqlite.Connection|None=None
    async def connect(self)->None:
        """Open SQLite, apply schema, and run safe additive migrations."""
        if self._db is not None:return
        self._db=await aiosqlite.connect(self.path);self._db.row_factory=aiosqlite.Row;await self._db.execute('PRAGMA journal_mode=WAL');await self._db.execute('PRAGMA busy_timeout=5000');await self._db.executescript(SCHEMA)
        cols=await self._table_columns('secret_events_log')
        for name,definition in [('revealed_at','TEXT DEFAULT NULL'),('revealed_by','INTEGER DEFAULT NULL'),('teaser_message_id','INTEGER DEFAULT NULL')]:
            if name not in cols:await self._db.execute(f'ALTER TABLE secret_events_log ADD COLUMN {name} {definition}')
        await self._db.commit()
    async def _table_columns(self,table:str)->set[str]:
        """Return existing column names for a table."""
        async with self.db.execute(f'PRAGMA table_info({table})') as cur:return {str(r[1]) for r in await cur.fetchall()}
    async def close(self)->None:
        """Close the SQLite connection safely."""
        if self._db is not None:await self._db.close();self._db=None
    @property
    def db(self)->aiosqlite.Connection:
        """Return the connected database."""
        if self._db is None:raise RuntimeError('Database is not connected')
        return self._db
    async def execute(self,sql:str,params:tuple=())->None:
        """Execute and commit a write.""";await self.db.execute(sql,params);await self.db.commit()
    async def fetchone(self,sql:str,params:tuple=())->aiosqlite.Row|None:
        """Fetch one row."""
        async with self.db.execute(sql,params) as cur:return await cur.fetchone()
    async def fetchall(self,sql:str,params:tuple=())->list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.db.execute(sql,params) as cur:return await cur.fetchall()
    async def upsert_member(self,user_id:int,group_id:int,username:str,name:str)->None:
        """Create or refresh a member without replacing learned fields.""";ts=now_ts();await self.execute("INSERT INTO members(user_id,group_id,username,preferred_name,last_seen,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,group_id) DO UPDATE SET username=excluded.username,last_seen=excluded.last_seen,preferred_name=CASE WHEN members.preferred_name='' THEN excluded.preferred_name ELSE members.preferred_name END",(user_id,group_id,username or '',name or '',ts,ts))
    async def increment_interaction(self,user_id:int,group_id:int)->None:
        """Increment member interaction count and last-seen time.""";await self.execute('UPDATE members SET interaction_count=interaction_count+1,last_seen=? WHERE user_id=? AND group_id=?',(now_ts(),user_id,group_id))
    async def add_memory(self,user_id:int,group_id:int,memory_type:str,content:str)->None:
        """Store bounded member memory.""";await self.execute('INSERT INTO member_memory(user_id,group_id,memory_type,content,created_at) VALUES(?,?,?,?,?)',(user_id,group_id,memory_type,content[:500],now_ts()));await self.execute('UPDATE member_memory SET is_active=0 WHERE id IN (SELECT id FROM member_memory WHERE user_id=? AND group_id=? AND memory_type=? AND is_active=1 ORDER BY created_at DESC LIMIT -1 OFFSET 10)',(user_id,group_id,memory_type))
    async def memories(self,user_id:int,group_id:int,memory_type:str|None=None,limit:int=10)->list[str]:
        """Return recent active memories.""";q='SELECT content FROM member_memory WHERE user_id=? AND group_id=? AND is_active=1';p=[user_id,group_id]
        if memory_type:q+=' AND memory_type=?';p.append(memory_type)
        q+=' ORDER BY created_at DESC LIMIT ?';p.append(limit);rows=await self.fetchall(q,tuple(p));return [str(r[0]) for r in rows]
    async def delete_memories_matching(self,user_id:int,group_id:int,term:str)->int:
        """Deactivate memories containing a requested term.""";cur=await self.db.execute('UPDATE member_memory SET is_active=0 WHERE user_id=? AND group_id=? AND is_active=1 AND content LIKE ?',(user_id,group_id,f'%{term}%'));await self.db.commit();return cur.rowcount
    async def set_cooldown(self,scope:str,scope_id:str,kind:str,expires_at:float)->None:
        """Create or replace a cooldown.""";await self.execute('INSERT INTO cooldowns(scope,scope_id,cooldown_type,expires_at) VALUES(?,?,?,?) ON CONFLICT(scope,scope_id,cooldown_type) DO UPDATE SET expires_at=excluded.expires_at',(scope,scope_id,kind,expires_at))
    async def cooldown_active(self,scope:str,scope_id:str,kind:str,at:float|None=None)->bool:
        """Return whether a cooldown is active.""";r=await self.fetchone('SELECT expires_at FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?',(scope,scope_id,kind));return bool(r and float(r[0])>(at or now_ts()))
    async def prune_cooldowns(self)->None:
        """Delete expired cooldown rows.""";await self.execute('DELETE FROM cooldowns WHERE expires_at<=?',(now_ts(),))
    async def get_active_wyr_session(self,group_id:int)->aiosqlite.Row|None:
        """Return the active WYR session for a group.""";return await self.fetchone("SELECT * FROM game_sessions WHERE group_id=? AND game_type='would_you_rather' AND is_active=1 ORDER BY id DESC LIMIT 1",(group_id,))
    async def update_wyr_votes(self,poll_id:str,user_id:int,option:int)->bool:
        """Atomically record or move a WYR vote."""
        if option not in (0,1):return False
        await self.db.execute('BEGIN IMMEDIATE')
        try:
            async with self.db.execute("SELECT id,state FROM game_sessions WHERE game_type='would_you_rather' AND is_active=1") as cur:rows=await cur.fetchall()
            import json
            found=None
            for r in rows:
                try:s=json.loads(r[1])
                except (TypeError,ValueError):continue
                if str(s.get('poll_id'))==str(poll_id):found=(int(r[0]),s);break
            if not found:await self.db.rollback();return False
            sid,state=found;uid=str(user_id);a=state.setdefault('voters_a',[]);b=state.setdefault('voters_b',[])
            if uid in a:a.remove(uid)
            if uid in b:b.remove(uid)
            (a if option==0 else b).append(uid)
            await self.db.execute('UPDATE game_sessions SET state=? WHERE id=? AND is_active=1',(json.dumps(state),sid));await self.db.commit();return True
        except Exception:await self.db.rollback();raise
    async def close_wyr_session(self,poll_id:str,result:dict)->bool:
        """Atomically close a WYR session and record its history."""
        import json
        await self.db.execute('BEGIN IMMEDIATE')
        try:
            async with self.db.execute("SELECT id,group_id,state FROM game_sessions WHERE game_type='would_you_rather' AND is_active=1") as cur:rows=await cur.fetchall()
            row=None
            for r in rows:
                try:
                    if str(json.loads(r[2]).get('poll_id'))==str(poll_id):row=r;break
                except (TypeError,ValueError):continue
            if not row:await self.db.rollback();return False
            sid,gid=int(row[0]),int(row[1]);cur=await self.db.execute('UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=? AND is_active=1',(now_ts(),sid))
            if cur.rowcount!=1:await self.db.rollback();return False
            await self.db.execute('INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)',(gid,'would_you_rather',None,json.dumps(result),now_ts()));await self.db.commit();return True
        except Exception:await self.db.rollback();raise
    async def get_secret_event(self,event_id:int)->aiosqlite.Row|None:
        """Fetch a complete secret event row.""";return await self.fetchone('SELECT * FROM secret_events_log WHERE id=?',(event_id,))
    async def is_revealed(self,event_id:int)->bool:
        """Return whether a secret event has already been revealed.""";r=await self.fetchone('SELECT revealed_at FROM secret_events_log WHERE id=?',(event_id,));return bool(r and r[0])
    async def mark_revealed(self,event_id:int,revealed_by:int|None,message_id:int|None)->bool:
        """Mark an event revealed using compare-and-set semantics.""";cur=await self.db.execute('UPDATE secret_events_log SET revealed_at=?,revealed_by=?,teaser_message_id=COALESCE(teaser_message_id,?) WHERE id=? AND revealed_at IS NULL',(str(now_ts()),revealed_by,message_id,event_id));await self.db.commit();return cur.rowcount==1
