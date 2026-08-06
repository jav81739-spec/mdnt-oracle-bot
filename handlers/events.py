from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes

custom_welcome = {}  # {chat_id: str}
custom_goodbye = {}  # {chat_id: str}
join_log = {}  # {chat_id: [names]}
leave_log = {}  # {chat_id: [names]}


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when someone joins or leaves — handles welcome/goodbye + logging."""
    result: ChatMemberUpdated = update.chat_member
    chat_id = update.effective_chat.id
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user

    was_member = old_status in ("member", "administrator", "creator")
    is_member = new_status in ("member", "administrator", "creator")

    if not was_member and is_member:
        # Someone joined
        join_log.setdefault(chat_id, [])
        join_log[chat_id].append(user.first_name)
        text = custom_welcome.get(chat_id, f"✨ Welcome to the group, {user.first_name}!")
        await context.bot.send_message(chat_id, text.replace("{name}", user.first_name))

    elif was_member and not is_member:
        # Someone left or was removed
        leave_log.setdefault(chat_id, [])
        leave_log[chat_id].append(user.first_name)
        text = custom_goodbye.get(chat_id, f"👋 {user.first_name} left the group.")
        await context.bot.send_message(chat_id, text.replace("{name}", user.first_name))
        # Best-effort re-invite DM — only works if user has started a chat with the bot before
        try:
            link = await context.bot.export_chat_invite_link(chat_id)
            await context.bot.send_message(user.id, f"Hey, you left {update.effective_chat.title}! Here's a link back in if you want it: {link}")
        except Exception:
            pass  # can't DM users who haven't started a chat with the bot — expected, not an error


async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome [text] — use {name} to insert the new member's name")
        return
    custom_welcome[update.effective_chat.id] = " ".join(context.args)
    await update.message.reply_text("✅ Welcome message updated.")


async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setgoodbye [text] — use {name} to insert the leaving member's name")
        return
    custom_goodbye[update.effective_chat.id] = " ".join(context.args)
    await update.message.reply_text("✅ Goodbye message updated.")


async def get_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("Admins only.")
        return
    try:
        link = await context.bot.export_chat_invite_link(update.effective_chat.id)
        await update.message.reply_text(f"🔗 Invite link: {link}")
    except Exception:
        await update.message.reply_text("Couldn't generate a link — make sure I have 'invite users' admin permission.")


async def show_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    names = join_log.get(chat_id, [])[-10:]
    if not names:
        await update.message.reply_text("No joins logged yet.")
        return
    await update.message.reply_text("📥 Recent joins:\n" + ", ".join(names))


async def show_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    names = leave_log.get(chat_id, [])[-10:]
    if not names:
        await update.message.reply_text("No leaves logged yet.")
        return
    await update.message.reply_text("📤 Recent leaves:\n" + ", ".join(names))
