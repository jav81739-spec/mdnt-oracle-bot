"""Small, bounded public-context lookup for conversational references.

This is deliberately assistive: it supplies context to the language model but
never turns every chat message into a web search. No credentials are required.
"""
from __future__ import annotations

import re
from urllib.parse import quote
import httpx

# Words that strongly suggest the member is discussing a current/public topic.
_TOPIC_MARKERS = re.compile(
    r"\b(movie|film|series|show|actor|actress|director|match|cricket|football|soccer|tennis|ipl|test|odi|t20|score|team|player|win|won|loss|news|headline|election|release|trailer|episode|season|album|song|concert|award)\b",
    re.I,
)

async def get_context(text: str) -> str:
    """Return a tiny factual context packet, or an empty string on failure."""
    value = (text or "").strip()
    if len(value) < 5 or len(value) > 700 or not _TOPIC_MARKERS.search(value):
        return ""
    try:
        async with httpx.AsyncClient(timeout=4.5, headers={"User-Agent": "MidnightOracle/1.0"}) as client:
            # Wikipedia is useful for named movies, people, teams and other public entities.
            search = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={"action":"query","format":"json","list":"search","srsearch":value,"srlimit":3,"utf8":1},
            )
            search.raise_for_status()
            hits = search.json().get("query", {}).get("search", [])
            if not hits:
                return ""
            title = str(hits[0].get("title", ""))
            if not title:
                return ""
            summary = await client.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"), safe=""),
            )
            if summary.status_code >= 400:
                return ""
            data = summary.json()
            extract = re.sub(r"\s+", " ", str(data.get("extract", ""))).strip()
            if not extract:
                return ""
            return f"Public context (verify against the user's exact claim; do not present this as private knowledge): {title} — {extract[:900]}"
    except Exception:
        return ""
