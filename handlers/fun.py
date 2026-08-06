import random
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention

ROASTS = [
    "you're the human version of a buffering icon",
    "you have the confidence of someone who's never seen their own search history read aloud",
    "you type like autocorrect gave up on you personally",
    "you're proof that WiFi isn't the only thing that disconnects randomly",
]

COMPLIMENTS = [
    "you make this chat 10x funnier just by existing in it",
    "your timing in this group is honestly unmatched",
    "you're the reason this group hasn't gone silent yet",
    "you bring main character energy to every conversation",
]

EIGHT_BALL_ANSWERS = [
    "It is certain.", "Without a doubt.", "Yes, definitely.",
    "Ask again later.", "Cannot predict now.", "Don't count on it.",
    "My sources say no.", "Very doubtful.", "Outlook good.",
]

VIBE_READS = [
    "the chat is giving 2am deep talk energy tonight 🌙",
    "everyone's a little unhinged right now, and honestly it's working 😭",
    "quiet storm vibes — something's brewing",
    "pure chaos, no notes, 10/10 energy",
]

QUOTES = [
    "\"Do it scared.\" — unknown",
    "\"Not all who wander are lost.\" — Tolkien",
    "\"Fall seven times, stand up eight.\" — Japanese proverb",
]


async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"🔥 {mention(target.id, target.first_name)}, {random.choice(ROASTS)}", parse_mode="Markdown"
    )


async def compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"💐 {mention(target.id, target.first_name)}, {random.choice(COMPLIMENTS)}", parse_mode="Markdown"
    )


async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /8ball [your question]")
        return
    await update.message.reply_text(f"🎱 {random.choice(EIGHT_BALL_ANSWERS)}")


async def vibe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌡️ Vibe check: {random.choice(VIBE_READS)}")


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📖 {random.choice(QUOTES)}")


async def poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /poll Question | Option1 | Option2 | Option3"""
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if len(parts) < 3:
        await update.message.reply_text("Usage: /poll Question | Option1 | Option2 | Option3 (up to 10 options)")
        return
    question, options = parts[0], parts[1:]
    await context.bot.send_poll(update.effective_chat.id, question=question, options=options, is_anonymous=False)


RANK_TIERS = [
    (0, "🌱 Newcomer"),
    (10, "🥉 Bronze"),
    (50, "🥈 Silver"),
    (150, "🥇 Gold"),
    (400, "💎 Diamond"),
    (1000, "👑 Legend"),
]


async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.friendship import message_counts
    from handlers.mentions import mention

    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    count = message_counts.get(chat_id, {}).get(target.id, {}).get("count", 0)
    tier = RANK_TIERS[0][1]
    for threshold, name in RANK_TIERS:
        if count >= threshold:
            tier = name
    await update.message.reply_text(
        f"{mention(target.id, target.first_name)}'s rank: *{tier}* ({count} messages)",
        parse_mode="Markdown",
    )
