"""Organic relationship commands: private mechanics, fresh human wording."""
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
    user = update.effective_user
    if not chat or not update.effective_message:
        return
    context = f"group relationship moment; members are represented only by the names supplied in the event; event={key}"
    text = await voice.render(raw, context=context, event_key=f"relationship:{chat.id}:{key}")
    await update.effective_message.reply_text(text or "hmm. leaving this one to the room. 🌙")


async def bond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or chat.type == "private":
        await update.effective_message.reply_text("Bring /bond into a group. It belongs to the room, not the DMs.")
        return
    members = [m for m in await _members(chat.id) if int(m.get("id", 0)) != user.id]
    if not members:
        await update.effective_message.reply_text("Give the room a little life first. Then ask me again.")
        return
    # The mechanics stay private. Activity and recency only influence the internal
    # pool; the public message never claims that a person's feelings were measured.
    weights = [max(1, int(m.get("msgs", 0))) for m in members]
    partner = random.Random(hashlib.sha256(f"{chat.id}:{user.id}:bond:{sum(weights)}".encode()).digest()).choices(members, weights=weights, k=1)[0]
    a = mention(user.id, user.first_name or "you")
    b = mention(int(partner["id"]), partner.get("name", "someone"))
    await _say(update, f"A small feeling in the room keeps putting {a} and {b} in the same sentence. I wouldn't over-explain it. Just notice it. 🌙", f"bond:{min(user.id,int(partner['id']))}:{max(user.id,int(partner['id']))}")


async def randomship(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("Try /randomship inside the group.")
        return
    members = await _members(chat.id)
    if len(members) < 2:
        await update.effective_message.reply_text("Not enough people in the room yet. Let it breathe.")
        return
    rng = _rng(chat.id, update.effective_user.id, "randomship")
    a, b = rng.sample(members, 2)
    await _say(update, f"For no particularly sensible reason, {mention(a['id'], a.get('name','someone'))} and {mention(b['id'], b.get('name','someone'))} have excellent trouble-making chemistry today. 😭", f"randomship:{min(a['id'],b['id'])}:{max(a['id'],b['id'])}")


async def matchmaker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.effective_message.reply_text("The matchmaker needs a room full of people.")
        return
    members = await _members(chat.id)
    if len(members) < 2:
        await update.effective_message.reply_text("Let a few more people talk first.")
        return
    rng = _rng(chat.id, update.effective_user.id, "matchmaker")
    a, b = rng.sample(members, 2)
    await _say(update, f"Something about {mention(a['id'], a.get('name','someone'))} and {mention(b['id'], b.get('name','someone'))} feels suspiciously well-timed. I'm not saying anything else. 👀", f"matchmaker:{min(a['id'],b['id'])}:{max(a['id'],b['id'])}")
