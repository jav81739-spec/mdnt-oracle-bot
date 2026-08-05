from telegram import Update
from telegram.ext import ContextTypes


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"User ID: {target.id}\nChat ID: {update.effective_chat.id}"
    )


async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    text = (
        f"👤 {target.first_name}\n"
        f"Username: @{target.username or 'none'}\n"
        f"ID: {target.id}"
    )
    await update.message.reply_text(text)


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /remind 10m Take a break")
        return

    time_str = context.args[0]
    reminder_text = " ".join(context.args[1:])

    unit = time_str[-1]
    try:
        amount = int(time_str[:-1])
    except ValueError:
        await update.message.reply_text("Time format: 10s, 10m, or 10h")
        return

    seconds = {"s": 1, "m": 60, "h": 3600}.get(unit)
    if not seconds:
        await update.message.reply_text("Time format: 10s, 10m, or 10h")
        return

    delay = amount * seconds
    chat_id = update.effective_chat.id
    user_mention = update.effective_user.mention_html()

    context.job_queue.run_once(
        lambda ctx: ctx.bot.send_message(chat_id, f"⏰ Reminder for {user_mention}: {reminder_text}", parse_mode="HTML"),
        when=delay,
    )
    await update.message.reply_text(f"Got it, I'll remind you in {time_str} ⏳")
