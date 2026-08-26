"""Persistent group lifecycle events and administrator utilities."""
from __future__ import annotations

import logging

from telegram import ChatMemberUpdated, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from core.storage import storage

log = logging.getLogger("midnight.events")
STORAGE_KEY = "events:v2"


def _fresh() -> dict:
    return {"chats": {}}


def _chat(state: dict, chat_id: int | str) -> dict:
    return state.setdefault("chats", {}).setdefault(
        str(chat_id),
        {"welcome": None, "goodbye": None, "joins": [], "leaves": []},
    )


async def _load() -> dict:
    state = await storage.load(STORAGE_KEY, _fresh())
    return state if isinstance(state, dict) else _fresh()


async def _save(state: dict) -> None:
    if not await storage.save(STORAGE_KEY, state):
        raise RuntimeError("event state could not be persisted")


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle joins/leaves with durable bounded logs."""
    result: ChatMemberUpdated = update.chat_member
    chat_id = update.effective_chat.id
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user

    was_member = old_status in ("member", "administrator", "creator")
    is_member = new_status in ("member", "administrator", "creator")
    if was_member == is_member:
        return

    async with storage.lock(f"events:{chat_id}", ttl=15, wait=2.0) as acquired:
        if not acquired:
            log.warning("Event state busy for chat_id=%s", chat_id)
            return
        state = await _load()
        chat = _chat(state, chat_id)
        if not was_member and is_member:
            chat["joins"] = (chat.get("joins") or [])[-99:] + [user.first_name]
            text = chat.get("welcome") or f"✨ Welcome to the group, {user.first_name}!"
            action = "join"
        else:
            chat["leaves"] = (chat.get("leaves") or [])[-99:] + [user.first_name]
            text = chat.get("goodbye") or f"👋 {user.first_name} left the group."
            action = "leave"
        await _save(state)

    await context.bot.send_message(chat_id, text.replace("{name}", user.first_name))

    if action == "leave":
        try:
            link = await context.bot.export_chat_invite_link(chat_id)
            await context.bot.send_message(
                user.id,
                f"Hey, you left {update.effective_chat.title}! Here's a link back in if you want it: {link}",
            )
        except TelegramError as exc:
            # Telegram can legitimately reject a DM when the user has never started
            # the bot; this is expected and must not break the event handler.
            log.info("Could not DM departed user_id=%s: %s", user.id, exc)


async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome [text] — use {name} for the new member's name")
        return
    cid = update.effective_chat.id
    async with storage.lock(f"events:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Event settings are busy — try again.")
            return
        state = await _load()
        _chat(state, cid)["welcome"] = " ".join(context.args)
        await _save(state)
    await update.message.reply_text("✅ Welcome message updated.")


async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setgoodbye [text] — use {name} for the leaving member's name")
        return
    cid = update.effective_chat.id
    async with storage.lock(f"events:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Event settings are busy — try again.")
            return
        state = await _load()
        _chat(state, cid)["goodbye"] = " ".join(context.args)
        await _save(state)
    await update.message.reply_text("✅ Goodbye message updated.")


async def get_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    try:
        link = await context.bot.export_chat_invite_link(update.effective_chat.id)
        await update.message.reply_text(f"🔗 Invite link: {link}")
    except TelegramError as exc:
        log.warning("Invite link generation failed for chat_id=%s: %s", update.effective_chat.id, exc)
        await update.message.reply_text("Couldn't generate a link — check my invite permission.")


async def show_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = await _load()
    names = (_chat(state, update.effective_chat.id).get("joins") or [])[-10:]
    if not names:
        await update.message.reply_text("No joins logged yet.")
        return
    await update.message.reply_text("📥 Recent joins:\n" + ", ".join(names))


async def show_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = await _load()
    names = (_chat(state, update.effective_chat.id).get("leaves") or [])[-10:]
    if not names:
        await update.message.reply_text("No leaves logged yet.")
        return
    await update.message.reply_text("📤 Recent leaves:\n" + ", ".join(names))
