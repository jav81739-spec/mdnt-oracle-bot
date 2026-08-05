import random
from telegram import Update
from telegram.ext import ContextTypes

bestie_pairs = {}  # {chat_id: [(user1_id, user2_id), ...]}

DUO_PREFIXES = ["Chaos", "Dream", "Menace", "Golden", "Rogue"]
DUO_SUFFIXES = ["Duo", "Squad", "Twins", "Crew"]


async def bestie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to your bestie's message with /bestie")
        return
    user1 = update.effective_user
    user2 = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    bestie_pairs.setdefault(chat_id, [])
    bestie_pairs[chat_id].append((user1.id, user2.id))
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
