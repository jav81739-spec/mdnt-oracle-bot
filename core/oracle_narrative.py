"""Durable, one-at-a-time serialized storytelling and world-gossip for Oracle Pulse."""
from __future__ import annotations

import json
import re
from typing import Any

from .ai import service
from .oracle_mind import _language_hint, _story_quality_ok

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
MAX_PARTS = 4
MIN_PARTS = 2
TARGET_PARTS = 3
MAX_PUBLIC_CHARS = 1200


def _fallback(kind: str, title: str, part: int, max_parts: int, canon: str) -> str:
    scenes = (
        "At 12:17, the tea stall owner found a house key inside a lemon. Nobody at the stall recognised it. He put it beside the cash box and carried on serving chai. An hour later, a woman walked in, saw the key, and laughed before she started crying.",
        "The old lift stopped between floors with three strangers inside. One complained about the heat; another checked the buttons twice. Then the youngest passenger quietly asked why the lift music was playing a song from her grandmother's funeral. Nobody touched the speaker.",
        "A blue envelope appeared beneath the library door every Thursday. There was never a name on it. This week the librarian opened it and found a photograph of the room taken from inside the locked cupboard behind her desk.",
        "The shopkeeper kept a broken watch in the window because he liked its face. One rainy afternoon it started ticking again. He turned it over and found a tiny note taped underneath: 'You finally came back.' He had no memory of leaving it there.",
    )
    scene = scenes[(part - 1) % len(scenes)]
    ending = "There was still one thing nobody had explained." if part < max_parts else "By closing time, the mystery had become an ordinary memory."
    if kind == "gossip":
        return f"☾ *{title}*\n*Part {part}*\n\n{scene}\n\n_{ending}_"
    return f"☾ *{title}*\n*Part {part}*\n\n{scene}\n\n_{ending}_"


def _clean_public_text(text: str) -> str:
    """Remove leaked planning/instruction language before narrative text reaches Telegram."""
    text = re.sub(r"(?im)^.*(?:continuity bible|keep continuity|reveal one meaningful new detail).*$(?:\n|$)", "", text)
    text = re.sub(r"(?im)^.*(?:parts already delivered|return json only|one message, not the whole story|internal continuity).*$(?:\n|$)", "", text)
    text = re.sub(r"(?im)^.*(?:planning instructions|field names|part-generation rules|internal notes).*$(?:\n|$)", "", text)
    return re.sub(r"\s{3,}", "\n\n", text).strip()[:MAX_PUBLIC_CHARS]


async def ensure(db) -> None:
    await db.execute(TABLE.split(";\nCREATE INDEX", 1)[0] + ";")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_oracle_narratives_group ON oracle_narratives(group_id,status,next_at)")


async def active(db, group_id: int):
    return await db.fetchone("SELECT * FROM oracle_narratives WHERE group_id=? AND status='active' ORDER BY id DESC LIMIT 1", (group_id,))


async def recent_titles(db, group_id: int, limit: int = 24) -> list[str]:
    rows = await db.fetchall("SELECT title FROM oracle_narratives WHERE group_id=? ORDER BY id DESC LIMIT ?", (group_id, limit))
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
    kind = kind if kind in {"story", "gossip"} else "story"
    old = await recent_titles(db, group_id)
    recent = ", ".join(old[:12]) or "none"
    public = "\n".join(f"- {str(x.get('text',''))[:240]}" for x in context[-8:])
    prompt = f"""You are Midnight Oracle. Start a genuinely original serialized {kind} for a Telegram group.
Do not write an 'AI story'. Write like a person who happened to notice something worth telling.
Begin with a concrete human moment: somebody doing something, somewhere, with a particular object, sound, mistake, habit, or exchange. Let the meaning emerge from what happens; do not announce a theme.
The story should have its own odd little logic, believable human behaviour, and one turn that feels discovered rather than manufactured. It may be funny, tender, eerie, mundane, or surprising. Vary the emotional temperature.
Never use generic midnight/cosmic language, fake profundity, stock suspense, a moral, a lesson, or a philosophical sign-off. Never force the room context into the plot.
Language: {language}. Recent titles to avoid: {recent}.
Usually make {TARGET_PARTS} parts, never fewer than {MIN_PARTS} or more than {MAX_PARTS}; only use multiple parts when the idea genuinely earns them.
Return JSON only: title, premise, canon, max_parts. Canon is private continuity data and must never be written to users.
Recent room atmosphere, usable only when naturally relevant:
{public or '- none'}"""
    try:
        obj = _parse_json((await service.generate(prompt, timeout=25.0) or ""))
    except Exception:
        obj = None
    if not obj:
        title = "The Key in the Lemon" if kind == "story" else "The Rumour With No Address"
        premise = "A tiny object turns up where it should not be."
        canon = "Keep the story grounded in specific human behaviour; do not explain the mystery too early."
        max_parts = TARGET_PARTS
    else:
        title = str(obj.get("title") or "A Small Strange Thing")[:120]
        premise = str(obj.get("premise") or "Something ordinary becomes unexpectedly significant.")[:700]
        canon = str(obj.get("canon") or premise)[:1800]
        try:
            max_parts = max(MIN_PARTS, min(MAX_PARTS, int(obj.get("max_parts", TARGET_PARTS))))
        except Exception:
            max_parts = TARGET_PARTS
    if title.casefold() in {x.casefold() for x in old}:
        title = f"{title} · {str(int(now * 1000))[-5:]}"
    await db.execute("INSERT INTO oracle_narratives(group_id,kind,title,premise,canon,part_no,max_parts,status,created_at,updated_at,next_at) VALUES(?,?,?,?,?,?,?,'active',?,?,?)", (group_id, kind, title, premise, canon, 0, max_parts, now, now, now))
    return await active(db, group_id)


async def _generate_part(title: str, premise: str, canon: str, kind: str, part: int, previous_part: int, max_parts: int, context: list[dict[str, Any]], language: str, attempt: int) -> dict[str, Any] | None:
    prompt = f"""You are Midnight Oracle writing Part {part} of {title!r}.
Write only the story itself. No preamble, no explanation, no writing commentary.
Make this feel observed and human, not generated: concrete action, natural dialogue or behaviour where useful, specific sensory detail only when it earns its place, and a turn that follows from the characters rather than from a formula.
Do not start with 'The night...', 'Someone noticed...', 'The obvious explanation...', 'The answer arrived...', 'It was a strange...', or any generic mystery opener. Do not end with a moral, lesson, 'the story continues', 'the end', or a philosophical summary.
Do not mention Midnight Oracle inside the narrative. Do not use the words prompt, JSON, continuity, canon, instructions, theme, generation, part-generation, or internal notes.
Continuity: {premise}
Private canon: {canon}
This is part {part} of at most {max_parts}; parts already delivered: {previous_part}.
Before the final part, leave a real unresolved consequence rather than an artificial cliffhanger. On the final part, resolve what actually matters and stop naturally.
Aim for 180-650 characters of narrative.
Language: {language}.
Attempt {attempt}: change the scene, opening rhythm, central detail, and ending from any previous attempt.
Return JSON only: {{"text":"...", "finished": true|false}}."""
    try:
        obj = _parse_json((await service.generate(prompt, timeout=25.0) or ""))
    except Exception:
        return None
    if not obj or not str(obj.get("text", "")).strip():
        return None
    text = _clean_public_text(str(obj["text"]).strip())
    if not text or not _story_quality_ok(text):
        return None
    return {"text": text, "finished": bool(obj.get("finished", False))}


async def _render_part(db, row, context: list[dict[str, Any]], language: str, now: float) -> tuple[str, bool, str, int]:
    previous_part = int(row[6]); part = previous_part + 1; max_parts = int(row[7])
    title = str(row[3]); premise = str(row[4]); canon = str(row[5]); kind = str(row[2])
    generated = None
    for attempt in range(3):
        generated = await _generate_part(title, premise, canon, kind, part, previous_part, max_parts, context, language, attempt)
        if generated:
            break
    if generated:
        text = generated["text"]
        finished = part >= MIN_PARTS and (generated["finished"] or part >= max_parts)
    else:
        text = _fallback(kind, title, part, max_parts, canon)
        finished = part >= max_parts
    next_at = now + MIN_GAP
    await db.execute("UPDATE oracle_narratives SET part_no=?,updated_at=?,next_at=?,status=?,completed_at=? WHERE id=? AND status='active'", (part, now, next_at, "completed" if finished else "active", now if finished else None, int(row[0])))
    return text, finished, kind, previous_part


async def rollback(db, narrative_id: int, previous_part: int, now: float) -> None:
    await db.execute("UPDATE oracle_narratives SET part_no=?,updated_at=?,next_at=?,status='active',completed_at=NULL WHERE id=?", (previous_part, now, now, int(narrative_id)))


async def maybe_deliver(db, application, group_id: int, kind: str, context: list[dict[str, Any]], now: float) -> tuple[str | None, str, str | None, int | None, int | None]:
    await ensure(db)
    row = await active(db, group_id)
    if row:
        if float(row[11]) > now:
            return None, "active_wait", str(row[2]), None, None
        text, finished, row_kind, previous_part = await _render_part(db, row, context, _language_hint(context), now)
        return text, "finished" if finished else "continued", row_kind, int(row[0]), previous_part
    if kind not in {"story", "gossip"}:
        return None, "no_narrative", None, None, None
    row = await _new_series(db, group_id, kind, context, _language_hint(context), now)
    text, finished, row_kind, previous_part = await _render_part(db, row, context, _language_hint(context), now)
    return text, "finished" if finished else "started", row_kind, int(row[0]), previous_part
