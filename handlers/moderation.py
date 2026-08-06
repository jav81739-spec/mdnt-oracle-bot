from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

warnings = {}  # {chat_id: {user_id: count}}
group_rules = {}  # {chat_id: str}


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


async def _get_target(update: Update):
    """Get the user being replied to (most reliable way to target someone)."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /mute")
        return
    await context.bot.restrict_chat_member(
        update.effective_chat.id, target.id, ChatPermissions(can_send_messages=False)
    )
    await update.message.reply_text(f"🔇 Muted {target.first_name}")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /unmute")
        return
    await context.bot.restrict_chat_member(
        update.effective_chat.id, target.id, ChatPermissions(can_send_messages=True)
    )
    await update.message.reply_text(f"🔊 Unmuted {target.first_name}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /ban")
        return
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 Banned {target.first_name}")


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /kick")
        return
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"👢 Kicked {target.first_name}")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /warn")
        return
    chat_id = update.effective_chat.id
    warnings.setdefault(chat_id, {})
    warnings[chat_id][target.id] = warnings[chat_id].get(target.id, 0) + 1
    count = warnings[chat_id][target.id]
    await update.message.reply_text(f"⚠️ {target.first_name} warned ({count}/3)")
    if count >= 3:
        await context.bot.ban_chat_member(chat_id, target.id)
        await update.message.reply_text(f"{target.first_name} reached 3 warnings and was banned.")


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rules = group_rules.get(chat_id, "No rules set yet. Admins can use /setrules to add them.")
    await update.message.reply_text(f"📜 Group Rules:\n{rules}")


async def check_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _get_target(update) or update.effective_user
    chat_id = update.effective_chat.id
    count = warnings.get(chat_id, {}).get(target.id, 0)
    await update.message.reply_text(f"⚠️ {target.first_name} has {count}/3 warnings")


async def clear_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    target = await _get_target(update)
    if not target:
        await update.message.reply_text("Reply to the user's message with /clearwarns")
        return
    chat_id = update.effective_chat.id
    if chat_id in warnings and target.id in warnings[chat_id]:
        warnings[chat_id][target.id] = 0
    await update.message.reply_text(f"🧹 Warnings cleared for {target.first_name}")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to pin with /pin")
        return
    await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
    await update.message.reply_text("📌 Pinned.")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    await context.bot.unpin_chat_message(update.effective_chat.id)
    await update.message.reply_text("📌 Unpinned.")


async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: reply to the message you want to purge FROM, with /purge [count]"""
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to a message with /purge [count] to delete that many messages after it")
        return
    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /purge [number]")
        return
    chat_id = update.effective_chat.id
    start_id = update.message.reply_to_message.message_id
    deleted = 0
    for msg_id in range(start_id, start_id + count):
        try:
            await context.bot.delete_message(chat_id, msg_id)
            deleted += 1
        except Exception:
            pass
    try:
        await update.message.delete()
    except Exception:
        pass
    confirmation = await context.bot.send_message(chat_id, f"🧹 Purged {deleted} messages")
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
    chat_id = update.effective_chat.id
    group_rules[chat_id] = " ".join(context.args)
    await update.message.reply_text("📜 Rules updated. Check them anytime with /rules")


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /lock media | /lock links | /lock all"""
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    lock_type = context.args[0].lower() if context.args else "all"
    chat_id = update.effective_chat.id
    if lock_type in ("media", "all"):
        await context.bot.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_photos=False,
                can_send_videos=False,
                can_send_other_messages=False,
            ),
        )
    await update.message.reply_text(f"🔒 Locked: {lock_type}")


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    chat_id = update.effective_chat.id
    await context.bot.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_other_messages=True,
        ),
    )
    await update.message.reply_text("🔓 Unlocked — normal permissions restored.")
