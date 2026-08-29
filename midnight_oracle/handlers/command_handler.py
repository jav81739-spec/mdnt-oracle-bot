"""Minimal aesthetic command surface for Phase 1."""
from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..generators.truth_generator import question
from ..memory_engine import MemoryEngine


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome a user without exposing internal implementation details."""
    await update.effective_message.reply_text("☾ Midnight Oracle\n\nSomeone in the room who remembers you.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the compact public command guide."""
    await update.effective_message.reply_text("☾ /oracle  talk\n/memory  group memory\n/mymemory  your memory\n/forget <topic>  forget\n/truth [level]  truth")


async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an original Truth question with answer/pass controls."""
    level = context.args[0] if context.args else "light"
    text = question(level)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Answer", callback_data="truth:answer"), InlineKeyboardButton("Pass", callback_data="truth:pass")]])
    await update.effective_message.reply_text(f"☾ {text}", reply_markup=markup)


async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bounded group memory categories without dumping private member details."""
    db = context.application.bot_data.get("oracle_db")
    if not db or update.effective_chat is None:
        await update.effective_message.reply_text("☾ Memory is quiet right now.")
        return
    rows = await db.fetchall("SELECT memory_type,COUNT(*) FROM member_memory WHERE group_id=? AND is_active=1 GROUP BY memory_type", (update.effective_chat.id,))
    summary = ", ".join(f"{r[0]} {r[1]}" for r in rows) or "nothing yet"
    await update.effective_message.reply_text(f"☾ Group memory: {summary}.")


async def mymemory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the requesting member's bounded memory, preferably in private chat."""
    if update.effective_user is None:
        return
    db = context.application.bot_data.get("oracle_db")
    if not db:
        await update.effective_message.reply_text("☾ Your memory is quiet right now.")
        return
    group_id = update.effective_chat.id if update.effective_chat and update.effective_chat.type != "private" else 0
    if group_id == 0:
        row = await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1", (update.effective_user.id,))
        group_id = int(row[0]) if row else 0
    if not group_id:
        await update.effective_message.reply_text("☾ We haven't built a memory together yet.")
        return
    engine = MemoryEngine(db)
    profile = await engine.get(update.effective_user.id, group_id)
    items = list(profile.interests[:2]) + list(profile.wins[:2]) + list(profile.themes[:2])
    text = "\n".join(f"• {x}" for x in items) if items else "Nothing heavy stored. Just the moments that mattered."
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("☾ I'll keep personal memory details private. Ask me in DM.")
    else:
        await update.effective_message.reply_text(f"☾ What I remember\n{text}")


async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forget matching memory items for the requesting member."""
    if not context.args or not update.effective_user:
        await update.effective_message.reply_text("Tell me what to forget: /forget <topic>")
        return
    db = context.application.bot_data.get("oracle_db")
    if not db:
        await update.effective_message.reply_text("☾ Memory is quiet right now.")
        return
    group_id = update.effective_chat.id if update.effective_chat and update.effective_chat.type != "private" else 0
    if not group_id:
        row = await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1", (update.effective_user.id,))
        group_id = int(row[0]) if row else 0
    count = await db.delete_memories_matching(update.effective_user.id, group_id, " ".join(context.args)) if group_id else 0
    await update.effective_message.reply_text("☾ Forgotten." if count else "☾ I couldn't find that memory.")
