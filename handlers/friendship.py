import random
from telegram import Update
from telegram.ext import ContextTypes

bestie_pairs = {}  # {chat_id: [(user1_id, user2_id), ...]}
declared_besties = {}  # {chat_id: {user_id: bestie_user_obj}}
message_counts = {}  # {chat_id: {user_id: count}} — feeds squad/loyalty

DUO_PREFIXES = ["Chaos", "Dream", "Menace", "Golden", "Rogue"]
DUO_SUFFIXES = ["Duo", "Squad", "Twins", "Crew"]

COMPAT_DESCRIPTIONS = [
    "unstoppable chaos energy together",
    "the kind of duo that finishes each other's sentences",
    "opposites who somehow just work",
    "a slow-burn friendship that's actually stronger than it looks",
    "constant bickering, zero actual beef",
]

LOYALTY_DESCRIPTIONS = [
    "shows up for every conversation without fail",
    "quiet but always watching, always here",
    "the definition of ride-or-die in this chat",
    "here for the vibes, not the drama",
]

SHIP_VERDICTS = {
    "low": ["chaotic and doomed 💀", "friends at best, enemies at worst 😭", "please never test this in real life"],
    "mid": ["could work with effort 🤞", "a slow burn romance novel", "50/50, coin flip energy"],
    "high": ["written in the stars ✨", "unreasonably perfect together", "get married already 💍"],
}


def _ship_name(name1: str, name2: str) -> str:
    half1 = name1[: max(1, len(name1) // 2)]
    half2 = name2[len(name2) // 2 :]
    return (half1 + half2).title()


async def ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Classic ship command: reply to someone to ship yourself with them,
    or reply is not required — provide two names as args instead."""
    if update.message.reply_to_message:
        user1 = update.effective_user
        user2 = update.message.reply_to_message.from_user
        name1, name2 = user1.first_name, user2.first_name
    elif len(context.args) >= 2:
        name1, name2 = context.args[0], context.args[1]
    else:
        await update.message.reply_text("Usage: reply to someone with /ship, or /ship [name1] [name2]")
        return

    score = random.randint(0, 100)
    bar_filled = "❤️" * (score // 10)
    bar_empty = "🖤" * (10 - score // 10)
    tier = "low" if score < 40 else "mid" if score < 75 else "high"
    verdict = random.choice(SHIP_VERDICTS[tier])
    ship_name = _ship_name(name1, name2)

    await update.message.reply_text(
        f"🚢 Shipping *{name1}* + *{name2}*\n\n"
        f"Ship name: *{ship_name}*\n"
        f"{bar_filled}{bar_empty} {score}%\n"
        f"_{verdict}_",
        parse_mode="Markdown",
    )


async def random_ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot picks TWO random active members from the group itself and ships
    them — fully bot-driven, no one chooses, no privacy concern since it's
    random and public, not a real feelings reveal."""
    chat_id = update.effective_chat.id
    pool = list(message_counts.get(chat_id, {}).items())
    if len(pool) < 2:
        await update.message.reply_text(
            "Not enough active members tracked yet — need at least 2 people "
            "who've sent a message since I joined. Chat a bit more first!"
        )
        return

    (id1, data1), (id2, data2) = random.sample(pool, 2)
    name1, name2 = data1["name"], data2["name"]

    score = random.randint(0, 100)
    bar_filled = "❤️" * (score // 10)
    bar_empty = "🖤" * (10 - score // 10)
    tier = "low" if score < 40 else "mid" if score < 75 else "high"
    verdict = random.choice(SHIP_VERDICTS[tier])
    ship_name = _ship_name(name1, name2)

    await update.message.reply_text(
        f"🎲 Random ship of the moment...\n\n"
        f"🚢 *{name1}* + *{name2}*\n"
        f"Ship name: *{ship_name}*\n"
        f"{bar_filled}{bar_empty} {score}%\n"
        f"_{verdict}_",
        parse_mode="Markdown",
    )


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Call this on every message to feed /squad's activity ranking."""
    if not update.effective_chat or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    message_counts.setdefault(chat_id, {})
    if user.id not in message_counts[chat_id]:
        message_counts[chat_id][user.id] = {"name": user.first_name, "count": 0}
    message_counts[chat_id][user.id]["count"] += 1


async def bestie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to your bestie's message with /bestie")
        return
    user1 = update.effective_user
    user2 = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    bestie_pairs.setdefault(chat_id, [])
    bestie_pairs[chat_id].append((user1.id, user2.id))
    declared_besties.setdefault(chat_id, {})
    declared_besties[chat_id][user1.id] = user2
    declared_besties[chat_id][user2.id] = user1
    await update.message.reply_text(
        f"💛 {user1.first_name} & {user2.first_name} are now official besties!"
    )


async def duo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /duo to generate a duo name")
        return
    user1 = update.effective_user
    user2 = update.message.reply_to_message.from_user
    name = f"{random.choice(DUO_PREFIXES)} {random.choice(DUO_SUFFIXES)}"
    await update.message.reply_text(
        f"🔗 {user1.first_name} + {user2.first_name} = *{name}*", parse_mode="Markdown"
    )


async def friendship_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /friendship to check compatibility")
        return
    user1 = update.effective_user
    user2 = update.message.reply_to_message.from_user
    score = random.randint(40, 100)
    desc = random.choice(COMPAT_DESCRIPTIONS)
    await update.message.reply_text(
        f"💫 {user1.first_name} + {user2.first_name}: *{score}%* compatible\n_{desc}_",
        parse_mode="Markdown",
    )


async def tag_bestie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bestie_user = declared_besties.get(chat_id, {}).get(user_id)
    if not bestie_user:
        await update.message.reply_text("You haven't declared a bestie yet — use /bestie (reply to their message) first")
        return
    await update.message.reply_text(f"📣 {update.effective_user.first_name} is calling for their bestie: @{bestie_user.username or bestie_user.first_name}")


async def squad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    counts = message_counts.get(chat_id, {})
    if not counts:
        await update.message.reply_text("Not enough activity data yet — chat more first!")
        return
    top = sorted(counts.items(), key=lambda x: x[1]["count"], reverse=True)[:4]
    names = [entry[1]["name"] for entry in top]
    await update.message.reply_text("👥 The most active squad right now:\n" + ", ".join(names))


async def loyalty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    score = random.randint(60, 100)
    desc = random.choice(LOYALTY_DESCRIPTIONS)
    await update.message.reply_text(f"🛡️ {target.first_name}'s loyalty score: *{score}/100*\n_{desc}_", parse_mode="Markdown")
