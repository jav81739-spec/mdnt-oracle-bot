"""Small, bounded member memory: names plus recent conversation snippets."""
from __future__ import annotations
import json, logging, time
log=logging.getLogger("midnight.memory")
_storage=None
MAX_SNIPPETS=8
async def init(storage):
    global _storage; _storage=storage
async def remember(chat_id,user_id,name,username,text):
    if not _storage or not text:return
    key=f"oracle:memory:{chat_id}:{user_id}"
    try:
        raw=_storage.get(key); raw=await raw if hasattr(raw,"__await__") else raw
        data=json.loads(raw) if raw else {}
        data["name"]=(name or "friend")[:60]; data["username"]=(username or "")[:64]
        snippets=list(data.get("snippets",[])); snippets.append({"t":int(time.time()),"text":text[:500]}); data["snippets"]=snippets[-MAX_SNIPPETS:]
        result=_storage.setex(key,60*60*24*30,json.dumps(data,ensure_ascii=False));
        if hasattr(result,"__await__"): await result
    except Exception: log.debug("member memory unavailable",exc_info=True)
async def get(chat_id,user_id):
    if not _storage:return {}
    try:
        raw=_storage.get(f"oracle:memory:{chat_id}:{user_id}"); raw=await raw if hasattr(raw,"__await__") else raw
        return json.loads(raw) if raw else {}
    except Exception:return {}
