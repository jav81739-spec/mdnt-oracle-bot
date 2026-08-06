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


async def start_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ Welcome to the Midnight Realm! Send /oracle or /help to begin.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌙 *Midnight Oracle — Commands*\n\n"
        "*💬 Chat*\n"
        "/chat — toggle AI chat mode\n"
        "/persona [style] — set bot personality\n\n"
        "*🎮 Games*\n"
        "/quiz /truth /dare /wyr /nhie\n"
        "/rps [rock/paper/scissors]\n"
        "/riddle + /riddleanswer [guess]\n"
        "/scramble + /unscramble [guess]\n"
        "/guess [1-20]\n"
        "/leaderboard — win rankings\n"
        "/dice /darts /basketball /bowling /football /slot\n\n"
        "*🌙 Aesthetic*\n"
        "/oracle [question] /tarot /aura /emojiaura\n"
        "/fate /lore /starsign [sign]\n"
        "/whisper — reply + secret text\n"
        "/confess [text] — anonymous\n\n"
        "*👥 Friendship*\n"
        "/bestie /duo /friendship /ship — reply to someone\n"
        "/tagbestie — ping your bestie\n"
        "/squad — most active members\n"
        "/loyalty — reply to check loyalty score\n\n"
        "*🎉 Fun*\n"
        "/roast /compliment — reply to target someone\n"
        "/8ball [question] /vibe /quote\n\n"
        "*🛠️ Utility*\n"
        "/id /info — reply to target a user\n"
        "/remind [time] [text] — e.g. /remind 10m stretch\n\n"
        "*⚙️ Admin (admins only)*\n"
        "/mute /unmute /ban /kick — reply to a user's message\n"
        "/warn — reply to warn a user (3 warns = auto-ban)\n"
        "/rules — show group rules"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
