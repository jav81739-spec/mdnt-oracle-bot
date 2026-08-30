"""Private owner control surface for Midnight Oracle.

Owner commands are intentionally absent from Telegram's public command menu.
They are read-only/control tools except for explicit broadcast/announcement
operations and never require group-admin privileges.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
PRIVATE_COMMANDS = {
    "owner", "broadcast", "obroadcast", "announce", "wherebot", "botwhere",
    "groups", "dmstats", "botstats", "status", "publiclink", "link", "whoisbot",
}


def _is_owner(update) -> bool:
    user = getattr(update, "effective_user", None)
    return bool(user and OWNER_ID and user.id == OWNER_ID)


async def _dm_registry(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    try:
        storage = context.application.bot_data.get("oracle_storage")
        if storage is None:
            return {}
        raw = storage.get("midnight:dm_registry")
        if hasattr(raw, "__await__"):
            raw = await raw
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


async def track_private_message(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Count unique private-chat users; never store their message content."""
    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    message = getattr(update, "effective_message", None)
    if not chat or chat.type != "private" or not user or not message:
        return
    try:
        storage = context.application.bot_data.get("oracle_storage")
        if storage is None:
            return
        registry = await _dm_registry(context)
        key = str(user.id)
        entry = registry.get(key, {"first_seen": int(time.time()), "messages": 0})
        entry["last_seen"] = int(time.time())
        entry["messages"] = int(entry.get("messages", 0)) + 1
        entry["name"] = (user.first_name or "friend")[:80]
        registry[key] = entry
        # Keep telemetry bounded; oldest users fall out after 5000 records.
        if len(registry) > 5000:
            oldest = sorted(registry, key=lambda k: registry[k].get("last_seen", 0))[:500]
            for k in oldest:
                registry.pop(k, None)
        result = storage.set("midnight:dm_registry", json.dumps(registry, ensure_ascii=False))
        if hasattr(result, "__await__"):
            await result
    except Exception:
        return


async def _reply(update, text: str) -> None:
    msg = getattr(update, "effective_message", None)
    if msg:
        await msg.reply_text(text, disable_web_page_preview=True)


async def owner(update, context) -> None:
    if not _is_owner(update):
        return
    await _reply(update, "☾ OWNER CONSOLE\n\n/broadcast · /wherebot · /groups · /dmstats · /botstats · /status · /publiclink")


async def status(update, context) -> None:
    if not _is_owner(update):
        return
    app = context.application
    scheduler = app.bot_data.get("oracle_scheduler")
    await _reply(update, "☾ ORACLE STATUS\n\n" +
                 f"polling: {'active' if app.running else 'not running'}\n"
                 f"scheduler: {'online' if scheduler else 'not attached'}\n"
                 f"database: {'connected' if app.bot_data.get('oracle_db') else 'not ready'}\n"
                 f"commands: {len([h for hs in getattr(app, 'handlers', {}).values() for h in hs])} handlers")


async def wherebot(update, context) -> None:
    if not _is_owner(update):
        return
    try:
        from startup import get_chat_registry
        registry = await get_chat_registry()
        groups = [v for v in registry.values() if v.get("type") in ("group", "supergroup")]
        channels = [v for v in registry.values() if v.get("type") == "channel"]
        lines = ["☾ ORACLE WHEREABOUTS", "", f"Groups known: {len(groups)}", f"Channels known: {len(channels)}"]
        if groups:
            lines.append("\nGroups:")
            for g in groups[:40]:
                lines.append(f"• {g.get('title') or 'untitled'}")
        if channels:
            lines.append("\nChannels:")
            for c in channels[:40]:
                lines.append(f"• {c.get('title') or 'untitled'}")
        await _reply(update, "\n".join(lines))
    except Exception:
        await _reply(update, "☾ I can't read the room map right now.")


async def groups(update, context) -> None:
    if not _is_owner(update):
        return
    try:
        from startup import get_chat_registry
        registry = await get_chat_registry()
        rows = []
        for cid, info in registry.items():
            if info.get("type") in ("group", "supergroup"):
                rows.append((info.get("title") or "untitled", cid, info.get("seen", 0)))
        rows.sort(key=lambda x: x[2], reverse=True)
        lines = [f"☾ GROUPS CONNECTED · {len(rows)}", ""]
        lines += [f"• {name} · {cid}" for name, cid, _ in rows[:60]]
        await _reply(update, "\n".join(lines))
    except Exception:
        await _reply(update, "☾ Group registry unavailable.")


async def dmstats(update, context) -> None:
    if not _is_owner(update):
        return
    registry = await _dm_registry(context)
    total = len(registry)
    active = sum(1 for v in registry.values() if int(v.get("last_seen", 0)) >= int(time.time()) - 86400 * 7)
    messages = sum(int(v.get("messages", 0)) for v in registry.values())
    await _reply(update, f"☾ PRIVATE ORBIT\n\nUnique DMs: {total}\nActive last 7 days: {active}\nMessages observed: {messages}\n\nOnly anonymous counters are kept here; message text is not stored.")


async def botstats(update, context) -> None:
    if not _is_owner(update):
        return
    registry = await _dm_registry(context)
    try:
        from startup import get_chat_registry
        chats = await get_chat_registry()
    except Exception:
        chats = {}
    groups = sum(1 for v in chats.values() if v.get("type") in ("group", "supergroup"))
    channels = sum(1 for v in chats.values() if v.get("type") == "channel")
    await _reply(update, f"☾ ORACLE NUMBERS\n\nGroups: {groups}\nChannels: {channels}\nPrivate DMs: {len(registry)}\nKnown destinations: {len(chats)}")


async def publiclink(update, context) -> None:
    if not _is_owner(update):
        return
    try:
        me = await context.bot.get_me()
        username = getattr(me, "username", None)
        if username:
            await _reply(update, f"☾ PUBLIC LINK\n\nhttps://t.me/{username}\n\nThe Oracle has a public Telegram username.")
        else:
            await _reply(update, "☾ PUBLIC LINK\n\nNo public username is currently available for this bot.\n\nUse Telegram's bot username settings to create one, then this command will show it automatically.")
    except Exception:
        await _reply(update, "☾ PUBLIC LINK\n\nTelegram did not return a public username right now. No link was invented.")


async def broadcast(update, context) -> None:
    if not _is_owner(update):
        return
    text = " ".join(getattr(context, "args", []) or []).strip()
    if not text:
        await _reply(update, "☾ BROADCAST\n\nUse /broadcast <update>.\nIt sends only to destinations Oracle has actually discovered.")
        return
    try:
        from startup import get_broadcast_targets
        targets = await get_broadcast_targets(True, True)
    except Exception:
        targets = []
    sent = failed = 0
    for chat_id in targets:
        try:
            await context.bot.send_message(chat_id, text, disable_web_page_preview=True)
            sent += 1
        except Exception:
            failed += 1
    await _reply(update, f"☾ BROADCAST COMPLETE\n\nDelivered: {sent}\nUnavailable: {failed}\nDestinations checked: {len(targets)}")


def register(app) -> None:
    """Attach private owner commands and DM counters without exposing them publicly."""
    if not OWNER_ID:
        return
    for name, callback in {
        "owner": owner, "broadcast": broadcast, "obroadcast": broadcast, "announce": broadcast,
        "wherebot": wherebot, "botwhere": wherebot, "groups": groups, "dmstats": dmstats,
        "botstats": botstats, "status": status, "publiclink": publiclink, "link": publiclink,
        "whoisbot": publiclink,
    }.items():
        app.add_handler(CommandHandler(name, callback), group=50)
    app.add_handler(MessageHandler(filters.ALL, track_private_message), group=-997)
    private = set(app.bot_data.get("private_commands", set()))
    private.update(PRIVATE_COMMANDS)
    app.bot_data["private_commands"] = private
