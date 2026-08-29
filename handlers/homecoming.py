"""One-time Midnight Oracle homecoming signal."""
from __future__ import annotations
import hashlib, json, random
from datetime import date
from telegram.constants import ParseMode

def _mention(member):
    username = (member.get("username") or "").strip()
    return f"@{username}" if username else member.get("name", "someone")

async def _get(storage, key):
    if not storage: return None
    try:
        result = storage.get(key)
        return await result if hasattr(result, "__await__") else result
    except Exception: return None

async def _set(storage, key, value, ttl=0):
    if not storage: return
    try:
        result = storage.setex(key, ttl, value) if ttl else storage.set(key, value)
        if hasattr(result, "__await__"): await result
    except Exception: pass

async def _members(storage, chat_id):
    raw = await _get(storage, f"mbr:{chat_id}")
    try: return json.loads(raw) if raw else []
    except Exception: return []

async def homecoming_job(ctx):
    try:
        from startup import get_broadcast_targets, _storage
        targets = await get_broadcast_targets(include_groups=True, include_channels=False)
        storage = _storage
    except Exception:
        return
    for chat_id in targets:
        done_key = f"homecoming:v1:{chat_id}"
        if await _get(storage, done_key): continue
        members = await _members(storage, chat_id)
        seed = int(hashlib.md5(f"homecoming-v1:{chat_id}:{date.today()}".encode()).hexdigest(), 16)
        rng = random.Random(seed)
        member = rng.choice(members) if members else None
        who = _mention(member) if member else "someone"
        messages = [
            f"🌙\n\n*midnight is home.*\n\n_{who}, you noticed._\n\n_let's see what the room becomes this time._\n\n✦ *— Midnight Oracle*",
            f"👁️ *THE ORACLE RETURNED*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n_no announcement. no ceremony._\n\n_just the feeling that something familiar is back._\n\n🌙 *— Midnight Oracle*",
            f"🖤 _the lights are back on._\n\n_{who} was still here in the dark._\n\n_now the Oracle is awake again._\n\n✦",
        ]
        try:
            await ctx.bot.send_message(chat_id, rng.choice(messages), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            await _set(storage, done_key, "1", ttl=86400 * 365)
        except Exception:
            continue
