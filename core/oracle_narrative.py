"""Durable, one-at-a-time serialized storytelling and world-gossip for Oracle Pulse."""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from typing import Any

from .ai import service
from .oracle_mind import _language_hint

TABLE = """
CREATE TABLE IF NOT EXISTS oracle_narratives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    premise TEXT NOT NULL,
    canon TEXT NOT NULL,
    part_no INTEGER NOT NULL DEFAULT 0,
    max_parts INTEGER NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    next_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_oracle_narratives_group ON oracle_narratives(group_id,status,next_at);
"""

MIN_GAP = 3 * 3600
MAX_PARTS = 7


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fallback(kind: str, title: str, part: int, max_parts: int, canon: str) -> str:
    seeds = [
        "The room had forgotten the first clue, which was probably why it mattered.",
        "Someone noticed a detail that had been sitting in plain sight the entire time.",
        "The obvious explanation lasted exactly until somebody asked one better question.",
        "By then, the little mystery had acquired a life of its own.",
        "Nobody agreed on what the clue meant, but everyone agreed they wanted to know the rest.",
        "The answer arrived quietly, almost embarrassed by how simple it was.",
        "And when the story finally ended, the strangest part was what everyone remembered.",
    ]
    line = seeds[min(part - 1, len(seeds) - 1)]
    if kind == "gossip":
        return f"☾ *{title}*\n*Part {part}*\n\n{line} {canon[:420]}\n\n_{'One more part remains.' if part < max_parts else 'That closes the file.'}_"
    return f"☾ *{title}*\n*Part {part}*\n\n{line}\n\n{canon[:520]}\n\n_{'The story continues.' if part < max_parts else 'The End.'}_"


async def ensure(db) -> None:
    await db.execute(TABLE.split(";\nCREATE INDEX", 1)[0] + ";")
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_oracle_narratives_group ON oracle_narratives(group_id,status,next_at)")
    except Exception:
        pass


async def active(db, group_id: int):
    return await db.fetchone(
        "SELECT * FROM oracle_narratives WHERE group_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (group_id,),
    )


async def recent_titles(db, group_id: int, limit: int = 24) -> list[str]:
    rows = await db.fetchall(
        "SELECT title FROM oracle_narratives WHERE group_id=? ORDER BY id DESC LIMIT ?",
        (group_id, limit),
    )
    return [str(r[0]) for r in rows]


def _parse_json(raw: str) -> dict[str, Any] | None:
    raw = raw.strip().strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


async def _new_series(db, group_id: int, kind: str, context: list[dict[str, Any]], language: str, now: float):
    old = await recent_titles(db, group_id)
    recent = ", ".join(old[:12]) or "none"
    public = "\n".join(f"- {str(x.get('text',''))[:240]}" for x in context[-8:])
    prompt = f"""You are Midnight Oracle writing a serialized Telegram group narrative.
Create a NEW {kind} series. It must be original and unlike these recently used titles: {recent}.
The series must feel written by a clever, emotionally perceptive human: specific, warm, occasionally funny, never robotic.
Language: {language}.
For story: original fiction only. For gossip: playful world/culture/idea gossip only; never invent allegations about real people or group members and never present fiction as real news.
Make 3-7 parts. Plan a real arc: setup, escalation, turn, consequence, ending. Do not cram the whole arc into Part 1.
Return JSON only with: title, premise, canon, max_parts. Canon is a concise internal continuity bible, not text to send to users.
Recent public room atmosphere:
{public or '- no usable context'}"""
    try:
        obj = _parse_json((await service.generate(prompt, timeout=25.0) or ""))
    except Exception:
        obj = None
    if not obj:
        title = "The Thing Nobody Noticed" if kind == "story" else "The Rumour With No Address"
        premise = "A small detail becomes impossible to ignore."
        canon = "Keep continuity coherent; reveal one meaningful new detail per part."
        max_parts = 4
    else:
        title = str(obj.get("title") or "Midnight File")[:120]
        premise = str(obj.get("premise") or "A small mystery grows. ")[:700]
        canon = str(obj.get("canon") or premise)[:1800]
        try:
            max_parts = max(3, min(MAX_PARTS, int(obj.get("max_parts", 4))))
        except Exception:
            max_parts = 4
    # Deterministic freshness guard against accidental same-title regeneration.
    if title.casefold() in {x.casefold() for x in old}:
        title = f"{title} · {now_ns_suffix(now)}"
    await db.execute(
        "INSERT INTO oracle_narratives(group_id,kind,title,premise,canon,part_no,max_parts,status,created_at,updated_at,next_at) VALUES(?,?,?,?,?,?,?,'active',?,?,?)",
        (group_id, kind, title, premise, canon, 0, max_parts, now, now, now),
    )
    return await active(db, group_id)


def now_ns_suffix(now: float) -> str:
    return str(int(now * 1000))[-5:]


async def _render_part(db, row, context: list[dict[str, Any]], language: str, now: float) -> tuple[str, bool]:
    part = int(row[6]) + 1
    max_parts = int(row[7])
    title = str(row[3]); premise = str(row[4]); canon = str(row[5]); kind = str(row[2])
    prior = f"Part {int(row[6])} was already delivered. Continue from the exact canon; do not recap unless a tiny reminder is natural."
    prompt = f"""You are Midnight Oracle. Write Part {part} of a serialized {kind} called {title!r} for a Telegram group.
This is one message, not the whole story. Keep continuity exact and advance the narrative meaningfully.
Voice: emotionally intelligent, conversational, vivid, restrained, occasionally witty; never robotic or purple-prose heavy.
Language: {language}.
Premise: {premise}
Continuity bible: {canon}
{prior}
The final part must resolve the thread. Earlier parts must leave a reason to return.
Return JSON only: {{"text":"...", "finished": true|false}}.
Text should include a subtle title/part marker but no meta explanation, no fake factual claims, and no member-targeted gossip.
Recent public atmosphere (use only if naturally relevant):
{chr(10).join('- '+str(x.get('text',''))[:220] for x in context[-5:])}"""
    try:
        obj = _parse_json((await service.generate(prompt, timeout=25.0) or ""))
    except Exception:
        obj = None
    if obj and str(obj.get("text", "")).strip():
        text = str(obj["text"]).strip()[:3200]
        finished = bool(obj.get("finished", part >= max_parts)) or part >= max_parts
    else:
        text = _fallback(kind, title, part, max_parts, canon)
        finished = part >= max_parts
    next_at = now + MIN_GAP
    await db.execute(
        "UPDATE oracle_narratives SET part_no=?,updated_at=?,next_at=?,status=?,completed_at=? WHERE id=? AND status='active'",
        (part, now, next_at, "completed" if finished else "active", now if finished else None, int(row[0])),
    )
    return text, finished


async def maybe_deliver(db, application, group_id: int, kind: str, context: list[dict[str, Any]], now: float) -> tuple[str | None, str]:
    """Return one due narrative part, or None. At most one narrative part is emitted per pulse target."""
    await ensure(db)
    row = await active(db, group_id)
    if row:
        if float(row[10]) > now:
            return None, "active_wait"
        text, finished = await _render_part(db, row, context, _language_hint(context), now)
        return text, "finished" if finished else "continued"
    row = await _new_series(db, group_id, kind, context, _language_hint(context), now)
    text, finished = await _render_part(db, row, context, _language_hint(context), now)
    return text, "finished" if finished else "started"
