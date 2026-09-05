"""Crash-safe compatibility surface for DeathGames survival actions.

The original handlers mutate game state and money in separate durable writes. These
handlers keep the same commands and state format but use idempotent economy
operations, so a crash/retry cannot pay twice or charge twice for the same state
transition.
"""
from __future__ import annotations

import datetime
import random

from telegram import Update
from telegram.ext import ContextTypes

from core.economy import EconomyError, service as economy
from core.storage import storage
from handlers import deathgames_v2 as engine


async def survive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await engine._load()
        chat = engine._chat(state, cid)
        record = chat["survival"].setdefault(uid, {"name": user.first_name, "streak": 0, "dead_until": None})
        record["name"] = user.first_name
        now = datetime.datetime.now(datetime.timezone.utc)
        if record.get("dead_until"):
            dead_until = datetime.datetime.fromisoformat(record["dead_until"])
            if now < dead_until:
                mins = int((dead_until - now).total_seconds() // 60)
                await update.message.reply_text(f"💀 You're still dead. Try again in ~{mins} min, or /revive for {engine.REVIVE_COST} coins.")
                return
            record["dead_until"] = None
        if random.random() < engine.SURVIVE_DIE_CHANCE:
            record["streak"] = 0
            record["dead_until"] = (now + datetime.timedelta(hours=engine.SURVIVE_DEATH_HOURS)).isoformat()
            await engine._save(state)
            text = f"☠️ {random.choice(engine.SURVIVAL_EVENTS_DEATH)}\n\nYou died. Streak reset. Locked out for {engine.SURVIVE_DEATH_HOURS}h, or /revive for {engine.REVIVE_COST} coins."
        else:
            next_streak = int(record.get("streak", 0)) + 1
            reward = engine.SURVIVE_BASE_REWARD + next_streak * engine.SURVIVE_STREAK_BONUS
            marker = f"survival:{cid}:{uid}:streak:{next_streak}"
            try:
                tx = await economy.add_once(user.id, reward, marker, reason="survival", scope=str(cid))
            except EconomyError as exc:
                await update.message.reply_text(f"⏳ Survival reward failed safely: {exc}")
                return
            record["streak"] = next_streak
            await engine._save(state)
            if tx.amount:
                text = f"❤️ {random.choice(engine.SURVIVAL_EVENTS_LIFE)}\n\nYou survived! Streak: {next_streak} 🔥 — +{reward} coins. Balance: {tx.balance}"
            else:
                text = f"❤️ Your previous survival reward was recovered safely. Streak: {next_streak} 🔥 — balance: {tx.balance}"
    await update.message.reply_text(text)


async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await engine._load()
        record = engine._chat(state, cid)["survival"].get(uid)
        if not record or not record.get("dead_until"):
            await update.message.reply_text("You're not dead right now.")
            return
        dead_until = str(record["dead_until"])
        marker = f"revive:{cid}:{uid}:{dead_until}"
        try:
            tx = await economy.remove_once(user.id, engine.REVIVE_COST, marker, reason="revive", scope=str(cid))
        except EconomyError:
            try:
                balance = await economy.balance(user.id, str(cid))
            except EconomyError:
                balance = "unavailable"
            await update.message.reply_text(f"Reviving costs {engine.REVIVE_COST} coins — you have {balance}.")
            return
        record["dead_until"] = None
        await engine._save(state)
    if tx.amount:
        await update.message.reply_text(f"✨ You paid {engine.REVIVE_COST} coins and came back to life. Balance: {tx.balance}")
    else:
        await update.message.reply_text(f"✨ Your previous revive charge was already settled safely. Balance: {tx.balance}")
