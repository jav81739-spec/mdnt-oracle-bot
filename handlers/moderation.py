"""Persistent, defensive moderation handlers for Midnight Oracle."""
from __future__ import annotations

import json

from telegram import Update, ChatPermissions
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from core.storage import storage


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ("administrator", "creator")
    except TelegramError:
        return False


async def _get_target(update: Update):
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


def _warning_key(chat_id: int, user_id: int) -> str:
    return f"moderation:warnings:{chat_id}:{user_id}"


def _rules_key(chat_id: int) -> str:
    return f"moderation:rules:{chat_id}"


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /mute")
        return
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"🔇 Muted {target.first_name}")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't mute that member. Check my admin permissions.")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /unmute")
        return
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔊 Unmuted {target.first_name}")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't unmute that member. Check my admin permissions.")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /ban")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"🚫 Banned {target.first_name}")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't ban that member. Check my admin permissions and hierarchy.")


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /kick")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"👢 Kicked {target.first_name}")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't kick that member. Check my admin permissions and hierarchy.")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /warn")
        return
    chat_id = update.effective_chat.id
    key = _warning_key(chat_id, target.id)
    async with storage.lock(f"warning:{chat_id}:{target.id}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Moderation is busy — try again.")
            return
        raw = await storage.get(key, "0")
        try:
            count = int(raw or 0) + 1
        except (TypeError, ValueError):
            count = 1
        await storage.set(key, str(count))
    await update.message.reply_text(f"⚠️ {target.first_name} warned ({count}/3)")
    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(f"{target.first_name} reached 3 warnings and was banned.")
        except TelegramError:
            await update.message.reply_text("⚠️ Three warnings reached, but I couldn't ban the member. Check my admin hierarchy.")


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = await storage.get(_rules_key(update.effective_chat.id), "")
    if not rules:
        rules = "No rules set yet. Admins can use /setrules to add them."
    await update.message.reply_text(f"📜 Group Rules:\n{rules}")


async def check_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _get_target(update) or update.effective_user
    raw = await storage.get(_warning_key(update.effective_chat.id, target.id), "0")
    try:
        count = int(raw or 0)
    except (TypeError, ValueError):
        count = 0
    await update.message.reply_text(f"⚠️ {target.first_name} has {count}/3 warnings")


async def clear_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /clearwarns")
        return
    await storage.delete(_warning_key(update.effective_chat.id, target.id))
    await update.message.reply_text(f"🧹 Warnings cleared for {target.first_name}")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to pin with /pin")
        return
    try:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Pinned.")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't pin that message. Check my admin permissions.")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    try:
        await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("📌 Unpinned.")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't unpin the message.")


async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete up to 100 message IDs beginning with the replied-to message."""
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to a message with /purge [1-100]")
        return
    try:
        count = int(context.args[0])
    except (TypeError, ValueError):
        await update.message.reply_text("Usage: /purge [1-100]")
        return
    if not 1 <= count <= 100:
        await update.message.reply_text("Choose a purge count between 1 and 100.")
        return
    chat_id = update.effective_chat.id
    start_id = update.message.reply_to_message.message_id
    deleted = 0
    for msg_id in range(start_id, start_id + count):
        try:
            await context.bot.delete_message(chat_id, msg_id)
            deleted += 1
        except TelegramError:
            continue
    try:
        await update.message.delete()
    except TelegramError:
        pass
    confirmation = await context.bot.send_message(chat_id, f"🧹 Purged {deleted} messages")
    if context.job_queue:
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id, confirmation.message_id), when=5
        )


async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setrules [your rules text]")
        return
    await storage.set(_rules_key(update.effective_chat.id), " ".join(context.args)[:4000])
    await update.message.reply_text("📜 Rules updated. Check them anytime with /rules")


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /lock media | /lock all."""
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    lock_type = context.args[0].lower() if context.args else "all"
    chat_id = update.effective_chat.id
    if lock_type == "media":
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_photos=False,
            can_send_videos=False,
            can_send_other_messages=False,
        )
    elif lock_type == "all":
        # Telegram's restricted-chat permission model requires text to be false
        # as well; the legacy implementation accidentally left text enabled.
        permissions = ChatPermissions(can_send_messages=False)
    else:
        await update.message.reply_text("Usage: /lock media | /lock all")
        return
    try:
        await context.bot.set_chat_permissions(chat_id, permissions)
        await update.message.reply_text(f"🔒 Locked: {lock_type}")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't change group permissions. Check my admin rights.")


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    try:
        await context.bot.set_chat_permissions(
            update.effective_chat.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_other_messages=True,
            ),
        )
        await update.message.reply_text("🔓 Unlocked — normal permissions restored.")
    except TelegramError:
        await update.message.reply_text("⚠️ I couldn't restore group permissions.")
