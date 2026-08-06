from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention
from handlers.friendship import message_counts


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    counts = message_counts.get(chat_id, {})
    total_messages = sum(u["count"] for u in counts.values())
    total_members = len(counts)
    await update.message.reply_text(
        f"📊 *Group Stats*\n\n"
        f"Tracked messages: {total_messages}\n"
        f"Active members seen: {total_members}\n\n"
        f"_(counts since I joined this chat)_",
        parse_mode="Markdown",
    )


async def top_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    counts = message_counts.get(chat_id, {})
    if not counts:
        await update.message.reply_text("No activity tracked yet — chat a bit first!")
        return
    ranked = sorted(counts.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    lines = [f"{i+1}. {mention(uid, data['name'])} — {data['count']} msgs" for i, (uid, data) in enumerate(ranked)]
    await update.message.reply_text("🏅 *Top Active Members*\n\n" + "\n".join(lines), parse_mode="Markdown")


async def msg_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    count = message_counts.get(chat_id, {}).get(target.id, {}).get("count", 0)
    await update.message.reply_text(f"💬 {mention(target.id, target.first_name)} has sent {count} tracked messages", parse_mode="Markdown")
