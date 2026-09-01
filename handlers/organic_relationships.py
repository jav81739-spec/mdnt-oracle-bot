"""Organic relationship commands with private mechanics and fresh public wording."""
from __future__ import annotations
import hashlib
import random
from telegram import Update
from telegram.ext import ContextTypes
from .mentions import mention
from midnight_oracle.generators.social_voice import voice


def _rng(chat_id: int, user_id: int, salt: str) -> random.Random:
    return random.Random(hashlib.sha256(f"{chat_id}:{user_id}:{salt}".encode()).digest())

async def _members(chat_id: int):
    try:
        from . import social_engine
        return await social_engine._members(chat_id)
    except Exception:
        return []

async def _say(update: Update, raw: str, key: str) -> None:
    chat = update.effective_chat
    if not chat or not update.effective_message:
        return
    text = await voice.render(raw, context=f"Telegram group relationship moment; event={key}", event_key=f"relationship:{chat.id}:{key}")
    await update.effective_message.reply_text(text or "hmm. leaving this one to the room. 🌙")

async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or chat.type == "private":
        await update.effective_message.reply_text("Bring /bond into a group. It belongs to the room.")
        return
    members = [m for m in await _members(chat.id) if int(m.get("id", 0)) != user.id]
    if not members:
        await update.effective_message.reply_text("Give the room a little life first. Then ask me again.")
        return
    weights = [max(1, int(m.get("msgs", 0))) for m in members]
    partner = random.Random(hashlib.sha256(f"{chat.id}:{user.id}:bond:{sum(weights)}".encode()).digest()).choices(members, weights=weights, k=1)[0]
    a, b = mention(user.id, user.first_name or "you"), mention(int(partner["id"]), partner.get("name", "someone"))
    await _say(update, f"{a} and {b} have a little something about the way they fit into this room. I wouldn't force a name onto it. 🌙", f"bond:{min(user.id,int(partner['id']))}:{max(user.id,int(partner['id']))}")

async def randomship(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("Try /randomship inside the group.")
        return
    members = await _members(chat.id)
    if len(members) < 2:
        await update.effective_message.reply_text("Not enough people in the room yet. Let it breathe.")
        return
    a, b = _rng(chat.id, update.effective_user.id, "randomship").sample(members, 2)
    await _say(update, f"For absolutely no serious reason, {mention(a['id'], a.get('name','someone'))} and {mention(b['id'], b.get('name','someone'))} have suspiciously good chemistry today. 👀", f"randomship:{min(a['id'],b['id'])}:{max(a['id'],b['id'])}")

async def matchmaker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("The matchmaker needs a room full of people.")
        return
    members = await _members(chat.id)
    if len(members) < 2:
        await update.effective_message.reply_text("Let a few more people talk first.")
        return
    a, b = _rng(chat.id, update.effective_user.id, "matchmaker").sample(members, 2)
    await _say(update, f"Something about {mention(a['id'], a.get('name','someone'))} and {mention(b['id'], b.get('name','someone'))} is making me look twice. That's all you're getting from me. 👀", f"matchmaker:{min(a['id'],b['id'])}:{max(a['id'],b['id'])}")

async def ship(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.effective_message.reply_to_message if update.effective_message else None
    if not reply or not reply.from_user or not update.effective_user:
        await update.effective_message.reply_text("Reply to someone's message with /ship. Let Midnight take it from there.")
        return
    a, b = update.effective_user, reply.from_user
    rng = _rng(update.effective_chat.id, a.id, f"ship:{b.id}")
    await _say(update, f"{mention(a.id,a.first_name)} + {mention(b.id,b.first_name)}\n\n{rng.choice(('there is a spark here, but I am not putting a number on it.','oddly good timing. I am choosing not to investigate further. 👀','this pairing has personality. that is enough of a verdict for tonight.','you two make the room slightly more interesting together.','I could explain it. I would rather leave it interesting.'))}", f"ship:{min(a.id,b.id)}:{max(a.id,b.id)}")

async def friendship(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.effective_message.reply_to_message if update.effective_message else None
    if not reply or not reply.from_user or not update.effective_user:
        await update.effective_message.reply_text("Reply to someone's message with /friendship. I'll take the hint from there.")
        return
    a, b = update.effective_user, reply.from_user
    await _say(update, f"{mention(a.id,a.first_name)} and {mention(b.id,b.first_name)} feel like the kind of pair that can survive a little chaos together. 🌙", f"friendship:{min(a.id,b.id)}:{max(a.id,b.id)}")

async def loyalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message else update.effective_user
    if target:
        await _say(update, f"{mention(target.id,target.first_name)} has a quiet kind of presence here. You notice it more when it's missing.", f"loyalty:{update.effective_chat.id}:{target.id}")
