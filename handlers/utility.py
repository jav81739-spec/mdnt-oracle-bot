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


afk_users = {}  # {chat_id: {user_id: reason}}


async def group_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    member_count = await context.bot.get_chat_member_count(chat.id)
    await update.message.reply_text(
        f"📋 *{chat.title}*\n"
        f"Chat ID: {chat.id}\n"
        f"Members: {member_count}\n"
        f"Type: {chat.type}",
        parse_mode="Markdown",
    )


async def set_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    reason = " ".join(context.args) if context.args else "No reason given"
    afk_users.setdefault(chat_id, {})
    afk_users[chat_id][user_id] = reason
    await update.message.reply_text(f"💤 {update.effective_user.first_name} is now AFK: {reason}")


async def check_afk_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Call on every message: if it replies to or mentions an AFK user, notify."""
    chat_id = update.effective_chat.id
    afk_dict = afk_users.get(chat_id, {})
    if not afk_dict:
        return

    # Clear AFK if the AFK user themself sends a message
    user_id = update.effective_user.id
    if user_id in afk_dict:
        del afk_dict[user_id]
        await update.message.reply_text(f"👋 Welcome back, {update.effective_user.first_name}! AFK status cleared.")
        return

    # Notify if replying to an AFK user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
        if target_id in afk_dict:
            name = update.message.reply_to_message.from_user.first_name
            await update.message.reply_text(f"💤 {name} is AFK: {afk_dict[target_id]}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to report with /report")
        return
    target = update.message.reply_to_message.from_user
    reporter = update.effective_user
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_tags = " ".join(f"@{a.user.username}" for a in admins if a.user.username and not a.user.is_bot)
    except Exception:
        admin_tags = ""
    await update.message.reply_text(
        f"🚩 {reporter.first_name} reported a message from {target.first_name}. {admin_tags}".strip()
    )


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
        "*💘 Secret Crush*\n"
        "/crush — reply to someone to privately pick them\n"
        "(only revealed if it's mutual — otherwise no one ever knows)\n"
        "/clearcrush — clear your current pick\n"
        "/randomship — bot randomly ships two active members\n"
        "/secretadmirer — bot DMs a random member an anonymous kind message\n\n"
        "*🛠️ Utility*\n"
        "/id /info — reply to target a user\n"
        "/remind [time] [text] — e.g. /remind 10m stretch\n\n"
        "*⚙️ Admin (admins only)*\n"
        "/mute /unmute /ban /kick — reply to a user's message\n"
        "/warn — reply to warn a user (3 warns = auto-ban)\n"
        "/warnings /clearwarns — reply to check/clear warnings\n"
        "/pin /unpin — reply to pin a message\n"
        "/purge [count] — reply + delete N messages\n"
        "/rules /setrules [text]\n"
        "/lock [media/all] /unlock\n"
        "/setwelcome [text] /setgoodbye [text] — use {name}\n"
        "/invite — get a fresh invite link\n\n"
        "*📊 Stats*\n"
        "/stats — group activity totals\n"
        "/topactive — ranked most active members\n"
        "/msgcount — reply to check someone's count\n"
        "/joined /left — recent join/leave logs\n\n"
        "*🛠️ More Utility*\n"
        "/groupinfo — group info card\n"
        "/afk [reason] — mark yourself away\n"
        "/report — reply to flag a message to admins\n"
        "/poll Question | A | B | C\n"
        "/rank — reply to check activity tier"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
