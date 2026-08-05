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
