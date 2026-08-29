"""Async SQLite persistence for Midnight Oracle, including additive Phase 2-4 tables."""
from __future__ import annotations
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, username TEXT DEFAULT '', preferred_name TEXT DEFAULT '', relationship_tier TEXT DEFAULT 'new', interaction_count INTEGER DEFAULT 0, last_seen REAL DEFAULT 0, interaction_preference TEXT DEFAULT 'lurker', created_at REAL NOT NULL, PRIMARY KEY(user_id, group_id));
CREATE TABLE IF NOT EXISTS member_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, memory_type TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS group_profile (group_id INTEGER PRIMARY KEY, group_name TEXT DEFAULT '', timezone TEXT NOT NULL, active_hours_start INTEGER DEFAULT 8, active_hours_end INTEGER DEFAULT 23, humour_level REAL DEFAULT .5, morning_active INTEGER DEFAULT 1, evening_active INTEGER DEFAULT 1, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cooldowns (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, scope_id TEXT NOT NULL, cooldown_type TEXT NOT NULL, expires_at REAL NOT NULL, UNIQUE(scope, scope_id, cooldown_type));
CREATE TABLE IF NOT EXISTS mood_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, energy REAL NOT NULL, humour REAL NOT NULL, social REAL NOT NULL, stress REAL NOT NULL, playful REAL NOT NULL, timestamp REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oracle_moments_log (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, moment_type TEXT NOT NULL, content TEXT NOT NULL, sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS scheduled_log (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, schedule_type TEXT NOT NULL, sent_at REAL NOT NULL, had_interaction INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS inside_jokes (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, joke_text TEXT NOT NULL, origin_message TEXT NOT NULL, first_seen REAL NOT NULL, last_referenced REAL NOT NULL, reference_count INTEGER DEFAULT 1, members_involved TEXT DEFAULT '', first_day INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, achievement_key TEXT NOT NULL, achieved_at REAL NOT NULL, is_secret INTEGER DEFAULT 0, is_revealed INTEGER DEFAULT 0, UNIQUE(user_id,group_id,achievement_key));
CREATE TABLE IF NOT EXISTS absence_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, last_active REAL NOT NULL, pinged_at REAL, ping_response TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sticker_events (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, trigger_context TEXT NOT NULL, sticker_id TEXT, sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS game_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, game_type TEXT NOT NULL, state TEXT NOT NULL, current_turn_user_id INTEGER, started_at REAL NOT NULL, ended_at REAL, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS game_history (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, game_type TEXT NOT NULL, winner_user_id INTEGER, summary TEXT DEFAULT '', played_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, predictor_user_id INTEGER NOT NULL, prediction_text TEXT NOT NULL, reveal_date REAL NOT NULL, actual_outcome TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS group_identity (group_id INTEGER PRIMARY KEY, humour_level REAL DEFAULT .5, depth_level REAL DEFAULT .5, activity_pattern TEXT DEFAULT 'scattered', favourite_topics TEXT DEFAULT '[]', quiet_periods TEXT DEFAULT '[]', peak_hours TEXT DEFAULT '[]', last_updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS secret_events_log (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, event_type TEXT NOT NULL, content TEXT NOT NULL, sent_at REAL NOT NULL);
"""

def now_ts() -> float:
    """Return the current UTC Unix timestamp."""
    return datetime.now(timezone.utc).timestamp()

class Database:
    """Own the SQLite connection and all persistence operations."""
    def __init__(self, path: str) -> None:
        """Create a database manager."""
        self.path = str(Path(path)); self._db: aiosqlite.Connection | None = None
    async def connect(self) -> None:
        """Open SQLite, enable WAL, and apply additive schema migrations."""
        if self._db is not None: return
        self._db = await aiosqlite.connect(self.path); self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL"); await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.executescript(SCHEMA); await self._db.commit()
    async def close(self) -> None:
        """Close SQLite safely."""
        if self._db is not None: await self._db.close(); self._db = None
    @property
    def db(self) -> aiosqlite.Connection:
        """Return the connected database."""
        if self._db is None: raise RuntimeError("Database is not connected")
        return self._db
    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute and commit a write statement."""
        await self.db.execute(sql, params); await self.db.commit()
    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Fetch one row."""
        async with self.db.execute(sql, params) as cursor: return await cursor.fetchone()
    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.db.execute(sql, params) as cursor: return await cursor.fetchall()
    async def upsert_member(self, user_id: int, group_id: int, username: str, name: str) -> None:
        """Create or refresh a member without overwriting learned fields."""
        ts=now_ts(); await self.execute("INSERT INTO members(user_id,group_id,username,preferred_name,last_seen,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,group_id) DO UPDATE SET username=excluded.username,last_seen=excluded.last_seen,preferred_name=CASE WHEN members.preferred_name='' THEN excluded.preferred_name ELSE members.preferred_name END", (user_id,group_id,username or '',name or '',ts,ts))
    async def increment_interaction(self,user_id:int,group_id:int)->None:
        """Increment interaction count and refresh last-seen time."""
        await self.execute("UPDATE members SET interaction_count=interaction_count+1,last_seen=? WHERE user_id=? AND group_id=?",(now_ts(),user_id,group_id))
    async def add_memory(self,user_id:int,group_id:int,memory_type:str,content:str)->None:
        """Store bounded memory and deactivate oldest overflow."""
        await self.execute("INSERT INTO member_memory(user_id,group_id,memory_type,content,created_at) VALUES(?,?,?,?,?)",(user_id,group_id,memory_type,content[:500],now_ts()))
        await self.execute("UPDATE member_memory SET is_active=0 WHERE id IN (SELECT id FROM member_memory WHERE user_id=? AND group_id=? AND memory_type=? AND is_active=1 ORDER BY created_at DESC LIMIT -1 OFFSET 10)",(user_id,group_id,memory_type))
    async def memories(self,user_id:int,group_id:int,memory_type:str|None=None,limit:int=10)->list[str]:
        """Return active recent memories."""
        q="SELECT content FROM member_memory WHERE user_id=? AND group_id=? AND is_active=1"; p=[user_id,group_id]
        if memory_type: q+=" AND memory_type=?"; p.append(memory_type)
        q+=" ORDER BY created_at DESC LIMIT ?"; p.append(limit); rows=await self.fetchall(q,tuple(p)); return [str(r[0]) for r in rows]
    async def delete_memories_matching(self,user_id:int,group_id:int,term:str)->int:
        """Deactivate memories matching a requested term."""
        cur=await self.db.execute("UPDATE member_memory SET is_active=0 WHERE user_id=? AND group_id=? AND is_active=1 AND content LIKE ?",(user_id,group_id,f"%{term}%")); await self.db.commit(); return cur.rowcount
    async def set_cooldown(self,scope:str,scope_id:str,kind:str,expires_at:float)->None:
        """Create or replace a cooldown."""
        await self.execute("INSERT INTO cooldowns(scope,scope_id,cooldown_type,expires_at) VALUES(?,?,?,?) ON CONFLICT(scope,scope_id,cooldown_type) DO UPDATE SET expires_at=excluded.expires_at",(scope,scope_id,kind,expires_at))
    async def cooldown_active(self,scope:str,scope_id:str,kind:str,at:float|None=None)->bool:
        """Return whether a cooldown is active."""
        row=await self.fetchone("SELECT expires_at FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?",(scope,scope_id,kind)); return bool(row and float(row[0])>(at or now_ts()))
    async def prune_cooldowns(self)->None:
        """Delete expired cooldowns."""
        await self.execute("DELETE FROM cooldowns WHERE expires_at<=?",(now_ts(),))
