"""Async SQLite persistence for Midnight Oracle."""
from __future__ import annotations

import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
 user_id INTEGER NOT NULL, group_id INTEGER NOT NULL, username TEXT DEFAULT '', preferred_name TEXT DEFAULT '',
 relationship_tier TEXT DEFAULT 'new', interaction_count INTEGER DEFAULT 0, last_seen REAL DEFAULT 0,
 interaction_preference TEXT DEFAULT 'lurker', created_at REAL NOT NULL, PRIMARY KEY(user_id, group_id));
CREATE TABLE IF NOT EXISTS member_memory (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL,
 memory_type TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS group_profile (
 group_id INTEGER PRIMARY KEY, group_name TEXT DEFAULT '', timezone TEXT NOT NULL,
 active_hours_start INTEGER DEFAULT 8, active_hours_end INTEGER DEFAULT 23, humour_level REAL DEFAULT .5,
 morning_active INTEGER DEFAULT 1, evening_active INTEGER DEFAULT 1, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cooldowns (
 id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, scope_id TEXT NOT NULL,
 cooldown_type TEXT NOT NULL, expires_at REAL NOT NULL, UNIQUE(scope, scope_id, cooldown_type));
CREATE TABLE IF NOT EXISTS mood_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, group_id INTEGER NOT NULL,
 energy REAL NOT NULL, humour REAL NOT NULL, social REAL NOT NULL, stress REAL NOT NULL,
 playful REAL NOT NULL, timestamp REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oracle_moments_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, moment_type TEXT NOT NULL,
 content TEXT NOT NULL, sent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS scheduled_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, schedule_type TEXT NOT NULL,
 sent_at REAL NOT NULL, had_interaction INTEGER DEFAULT 0);
"""


def now_ts() -> float:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).timestamp()


class Database:
    """Own the SQLite connection lifecycle and all phase-one persistence operations."""

    def __init__(self, path: str) -> None:
        """Create a database manager for the supplied SQLite path."""
        self.path = str(Path(path))
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open SQLite and create the complete schema."""
        if self._db is not None:
            return
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        """Close the SQLite connection safely."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Return the active connection or raise a clear programming error."""
        if self._db is None:
            raise RuntimeError("Database is not connected")
        return self._db

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a write statement and commit it."""
        await self.db.execute(sql, params)
        await self.db.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Fetch one row from SQLite."""
        async with self.db.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Fetch all rows from SQLite."""
        async with self.db.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def upsert_member(self, user_id: int, group_id: int, username: str, name: str) -> None:
        """Create or refresh a member record while preserving learned fields."""
        ts = now_ts()
        await self.execute("""INSERT INTO members(user_id,group_id,username,preferred_name,last_seen,created_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,group_id) DO UPDATE SET username=excluded.username,
        last_seen=excluded.last_seen, preferred_name=CASE WHEN members.preferred_name='' THEN excluded.preferred_name ELSE members.preferred_name END""",
        (user_id, group_id, username or "", name or "", ts, ts))

    async def increment_interaction(self, user_id: int, group_id: int) -> None:
        """Increment a member's meaningful interaction counter."""
        await self.execute("UPDATE members SET interaction_count=interaction_count+1,last_seen=? WHERE user_id=? AND group_id=?", (now_ts(), user_id, group_id))

    async def add_memory(self, user_id: int, group_id: int, memory_type: str, content: str) -> None:
        """Store one bounded memory item and deactivate the oldest overflow."""
        await self.execute("INSERT INTO member_memory(user_id,group_id,memory_type,content,created_at) VALUES(?,?,?,?,?)", (user_id, group_id, memory_type, content[:500], now_ts()))
        await self.execute("""UPDATE member_memory SET is_active=0 WHERE id IN (
          SELECT id FROM member_memory WHERE user_id=? AND group_id=? AND memory_type=? AND is_active=1
          ORDER BY created_at DESC LIMIT -1 OFFSET 10)""", (user_id, group_id, memory_type))

    async def memories(self, user_id: int, group_id: int, memory_type: str | None = None, limit: int = 10) -> list[str]:
        """Return recent active memories for a member."""
        if memory_type:
            rows = await self.fetchall("SELECT content FROM member_memory WHERE user_id=? AND group_id=? AND memory_type=? AND is_active=1 ORDER BY created_at DESC LIMIT ?", (user_id, group_id, memory_type, limit))
        else:
            rows = await self.fetchall("SELECT content FROM member_memory WHERE user_id=? AND group_id=? AND is_active=1 ORDER BY created_at DESC LIMIT ?", (user_id, group_id, limit))
        return [str(r[0]) for r in rows]

    async def delete_memories_matching(self, user_id: int, group_id: int, term: str) -> int:
        """Deactivate memories containing a user-requested term."""
        cur = await self.db.execute("UPDATE member_memory SET is_active=0 WHERE user_id=? AND group_id=? AND is_active=1 AND content LIKE ?", (user_id, group_id, f"%{term}%"))
        await self.db.commit()
        return cur.rowcount

    async def set_cooldown(self, scope: str, scope_id: str, kind: str, expires_at: float) -> None:
        """Create or replace a cooldown expiry."""
        await self.execute("""INSERT INTO cooldowns(scope,scope_id,cooldown_type,expires_at) VALUES(?,?,?,?)
        ON CONFLICT(scope,scope_id,cooldown_type) DO UPDATE SET expires_at=excluded.expires_at""", (scope, scope_id, kind, expires_at))

    async def cooldown_active(self, scope: str, scope_id: str, kind: str, at: float | None = None) -> bool:
        """Return whether a cooldown is currently active."""
        row = await self.fetchone("SELECT expires_at FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?", (scope, scope_id, kind))
        return bool(row and float(row[0]) > (at or now_ts()))

    async def prune_cooldowns(self) -> None:
        """Remove expired cooldown records."""
        await self.execute("DELETE FROM cooldowns WHERE expires_at <= ?", (now_ts(),))
