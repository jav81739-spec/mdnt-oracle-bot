"""Owner-only, read-only Telegram recovery audit for Midnight Oracle."""
from __future__ import annotations

import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import startup


def _owner_id() -> int:
    try:
        return int(os.getenv("OWNER_ID", "0") or 0)
    except ValueError:
        return 0


def _allowed(update: Update) -> bool:
    return bool(
        update.effective_user
        and update.effective_user.id == _owner_id()
        and update.effective_chat
        and update.effective_chat.type == "private"
    )


async def recover_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Audit every known chat without sending to or modifying any chat."""
    if not _allowed(update):
        return

    try:
        me = await context.bot.get_me()
    except Exception as exc:
        await update.effective_message.reply_text(f"☾ Recovery audit failed at Telegram authentication.\n{type(exc).__name__}: {exc}")
        return

    registry = await startup.get_chat_registry()
    if not registry:
        await update.effective_message.reply_text(
            "☾ MIDNIGHT RECOVERY\n\n"
            f"Bot: @{me.username or 'unknown'} · {me.id}\n"
            "Known destination registry: 0\n\n"
            "No destination records are currently available in persistent storage. "
            "I will not invent or probe unknown chats."
        )
        return

    counts = {"active": 0, "left": 0, "kicked": 0, "unavailable": 0, "error": 0}
    lines = [
        "☾ MIDNIGHT RECOVERY",
        "┄" * 18,
        f"Bot: @{me.username or 'unknown'} · {me.id}",
        f"Known destinations: {len(registry)}",
        "",
    ]

    for cid_text, info in sorted(registry.items(), key=lambda item: (str(item[1].get("title", "")).lower() if isinstance(item[1], dict) else "")):
        try:
            chat_id = int(cid_text)
        except (TypeError, ValueError):
            continue

        title = str(info.get("title", "Untitled"))[:80] if isinstance(info, dict) else "Untitled"
        try:
            chat = await context.bot.get_chat(chat_id)
            member = await context.bot.get_chat_member(chat_id, me.id)
            status = str(getattr(member, "status", "unknown"))
            if status in {"creator", "administrator", "member", "restricted"}:
                state = "active"
            elif status == "left":
                state = "left"
            elif status == "kicked":
                state = "kicked"
            else:
                state = "unavailable"
            counts[state] += 1
            lines.append(f"• {title} [{chat.type}] → {state} ({status})")
        except Exception as exc:
            counts["unavailable"] += 1
            detail = str(exc).replace("\n", " ")[:180]
            lines.append(f"• {title} [{cid_text}] → unavailable ({type(exc).__name__}: {detail})")

    lines.extend([
        "",
        f"🟢 Active: {counts['active']}",
        f"🟡 Left: {counts['left']}",
        f"🔴 Kicked: {counts['kicked']}",
        f"⚫ Unavailable: {counts['unavailable']}",
        "",
        "Read-only audit. No join, add, message, or membership change was attempted.",
    ])

    # Telegram messages have a size limit; keep the owner report bounded.
    await update.effective_message.reply_text("\n".join(lines)[:3900])


def register(app: Application) -> None:
    app.add_handler(CommandHandler("recover", recover_command), group=90)
