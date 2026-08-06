"""
Secret Crush — the group-safe version of what dating bots call "crush matching."
No one's pick is ever revealed unless it's mutual. If A picks B and B never
picks A, nobody finds out — including B.
"""
from telegram import Update
from telegram.ext import ContextTypes

# {chat_id: {user_id: target_user_id}}
crushes = {}


async def set_crush(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: reply to someone's message with /crush"""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Reply to someone's message with /crush to (privately) pick them.\n"
            "Nobody finds out unless it's mutual 🤫"
        )
        return

    sender = update.effective_user
    target = update.message.reply_to_message.from_user

    if target.id == sender.id:
        await update.message.reply_text("You can't crush on yourself 😭 (well, self-love counts too, but not here)")
        return

    chat_id = update.effective_chat.id
    crushes.setdefault(chat_id, {})
    crushes[chat_id][sender.id] = target.id

    # Try to delete the command message so no one in the group sees who was targeted
    try:
        await update.message.delete()
    except Exception:
        pass

    # Check for mutual match
    target_pick = crushes[chat_id].get(target.id)
    if target_pick == sender.id:
        await context.bot.send_message(
            chat_id,
            f"💘 It's a match! {sender.first_name} and {target.first_name} both picked each other!",
        )
        # Clear both so they can be re-matched fresh later if they want
        del crushes[chat_id][sender.id]
        del crushes[chat_id][target.id]
    else:
        # Confirm privately via DM so the group never sees it
        try:
            await context.bot.send_message(sender.id, f"🤫 Noted. If {target.first_name} picks you back, you'll both find out.")
        except Exception:
            await update.message.reply_text(
                "🤫 Got it — but I couldn't DM you the confirmation. "
                "Start a private chat with me first so I can message you directly next time."
            )


async def clear_crush(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id in crushes and user_id in crushes[chat_id]:
        del crushes[chat_id][user_id]
        await update.message.reply_text("🧹 Your pick has been cleared.")
    else:
        await update.message.reply_text("You don't have an active pick right now.")


ADMIRER_LINES = [
    "someone in this group thinks you brighten up the chat",
    "someone here secretly thinks you're the funniest one in this group",
    "someone thinks you don't get enough credit for how much you help others out",
    "someone here low-key admires how confident you are",
]


async def secret_admirer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot randomly picks an active member and sends them an anonymous
    kind message — fully bot-generated, not from a real person, so there's
    no identity to protect or reveal. Purely a feel-good random feature."""
    from handlers.friendship import message_counts  # local import avoids circular import

    chat_id = update.effective_chat.id
    pool = list(message_counts.get(chat_id, {}).items())
    if not pool:
        await update.message.reply_text("Not enough activity tracked yet — chat a bit more first!")
        return

    target_id, data = random.choice(pool)
    line = random.choice(ADMIRER_LINES)

    try:
        await context.bot.send_message(target_id, f"💌 Secret admirer alert: {line} 🤫")
        await update.message.reply_text("💌 A secret admirer message has been sent to someone in this group...")
    except Exception:
        await update.message.reply_text(
            f"Couldn't DM {data['name']} — they need to start a private chat with me first."
        )
