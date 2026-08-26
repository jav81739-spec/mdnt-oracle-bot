"""Midnight group economy handlers backed by the core economy engine."""
from __future__ import annotations

import datetime
import json
import random

from telegram import Update
from telegram.ext import ContextTypes

from handlers.mentions import mention
from core.economy import EconomyError, service as economy
from core.storage import storage

DAILY_AMOUNT = 100
ROB_SUCCESS_CHANCE = 0.4
ROB_STEAL_PERCENT = 0.25
ROB_FAIL_PENALTY = 50


def _scope(chat_id: int) -> str:
    return str(chat_id)


async def _register(chat_id: int, user_id: int, name: str) -> None:
    key = f"economy:members:{chat_id}"
    async with storage.lock(f"economy-members:{chat_id}") as acquired:
        if not acquired:
            return
        raw = await storage.get(key, "[]")
        try:
            members = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except (TypeError, ValueError):
            members = []
        by_id = {int(x.get("id")): x for x in members if isinstance(x, dict) and str(x.get("id", "")).lstrip("-").isdigit()}
        by_id[int(user_id)] = {"id": int(user_id), "name": str(name or "Member")[:80]}
        await storage.set(key, list(by_id.values()))


async def load_from_storage() -> None:
    """One-time migration from the legacy giant ``economy`` JSON blob."""
    marker = "economy:migration:v2"
    if await storage.exists(marker):
        return
    async with storage.lock("economy-migration", ttl=30, wait=1) as acquired:
        if not acquired or await storage.exists(marker):
            return
        raw = await storage.get("economy", "{}")
        try:
            legacy = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError):
            legacy = {}
        if isinstance(legacy, dict):
            for chat_id, accounts in legacy.items():
                if not isinstance(accounts, dict):
                    continue
                for uid, data in accounts.items():
                    if not isinstance(data, dict):
                        continue
                    try:
                        user_id = int(uid)
                        coins = max(0, int(data.get("coins", 0)))
                    except (TypeError, ValueError):
                        continue
                    await storage.set(economy.key(user_id, str(chat_id)), str(coins))
                    await _register(int(chat_id), user_id, str(data.get("name", "Member")))
                    if data.get("last_daily"):
                        await storage.set(f"economy:daily:{chat_id}:{user_id}", str(data["last_daily"]))
        await storage.set(marker, "1")


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    await _register(chat_id, user.id, user.first_name)
    key = f"economy:daily:{chat_id}:{user.id}"
    today = datetime.date.today().isoformat()
    async with storage.lock(f"economy-daily:{chat_id}:{user.id}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Midnight is processing your claim — try again in a moment.")
            return
        if await storage.get(key, "") == today:
            await update.message.reply_text("⏳ You already claimed today's coins — come back tomorrow!")
            return
        await economy.add(user.id, DAILY_AMOUNT, "daily", scope=_scope(chat_id))
        await storage.set(key, today)
    balance = await economy.balance(user.id, _scope(chat_id))
    await update.message.reply_text(f"💰 +{DAILY_AMOUNT} coins claimed! Balance: {balance}")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    await _register(chat_id, target.id, target.first_name)
    coins = await economy.balance(target.id, _scope(chat_id))
    await update.message.reply_text(
        f"💰 {mention(target.id, target.first_name)}'s balance: *{coins}* coins",
        parse_mode="Markdown",
    )


async def rob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /rob to try robbing them")
        return
    chat_id = update.effective_chat.id
    robber = update.effective_user
    victim = update.message.reply_to_message.from_user
    if robber.id == victim.id:
        await update.message.reply_text("You can't rob yourself 😭")
        return
    await _register(chat_id, robber.id, robber.first_name)
    await _register(chat_id, victim.id, victim.first_name)
    scope = _scope(chat_id)
    async with storage.lock(f"economy:{scope}:{min(robber.id, victim.id)}") as first_lock:
        if not first_lock:
            await update.message.reply_text("⏳ Economy is busy — try again.")
            return
        async with storage.lock(f"economy:{scope}:{max(robber.id, victim.id)}") as second_lock:
            if not second_lock:
                await update.message.reply_text("⏳ Economy is busy — try again.")
                return
            victim_balance = await economy.balance(victim.id, scope)
            if victim_balance < 20:
                await update.message.reply_text(f"{victim.first_name} is too broke to rob 💀")
                return
            if random.random() < ROB_SUCCESS_CHANCE:
                stolen = max(1, int(victim_balance * ROB_STEAL_PERCENT))
                try:
                    await economy.transfer(victim.id, robber.id, stolen, "rob", scope)
                except EconomyError:
                    await update.message.reply_text("⏳ The heist hit a concurrency snag — try again.")
                    return
                await update.message.reply_text(
                    f"🥷 {mention(robber.id, robber.first_name)} successfully robbed "
                    f"{stolen} coins from {mention(victim.id, victim.first_name)}!",
                    parse_mode="Markdown",
                )
            else:
                try:
                    await economy.remove(robber.id, ROB_FAIL_PENALTY, "rob-fine", scope)
                except EconomyError:
                    pass
                await update.message.reply_text(
                    f"🚨 {mention(robber.id, robber.first_name)} got caught robbing "
                    f"{mention(victim.id, victim.first_name)} and paid a {ROB_FAIL_PENALTY} coin fine!",
                    parse_mode="Markdown",
                )


async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    await _register(chat_id, user.id, user.first_name)
    if not context.args:
        await update.message.reply_text("Usage: /gamble [amount]")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Enter a valid number")
        return
    if amount <= 0:
        await update.message.reply_text("Enter a positive amount")
        return
    scope = _scope(chat_id)
    async with storage.lock(f"economy:{scope}:{user.id}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Economy is busy — try again.")
            return
        balance_now = await economy.balance(user.id, scope)
        if amount > balance_now:
            await update.message.reply_text(f"You only have {balance_now} coins")
            return
        try:
            if random.random() < 0.5:
                await economy.add(user.id, amount, "gamble-win", scope)
                await update.message.reply_text(f"🎰 You won! +{amount} coins. Balance: {balance_now + amount}")
            else:
                await economy.remove(user.id, amount, "gamble-loss", scope)
                await update.message.reply_text(f"💸 You lost {amount} coins. Balance: {balance_now - amount}")
        except EconomyError:
            await update.message.reply_text("⏳ The gamble couldn't be committed safely. Try again.")


async def economy_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    raw = await storage.get(f"economy:members:{chat_id}", "[]")
    try:
        members = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        members = []
    if not members:
        await update.message.reply_text("No accounts yet — use /daily to get started!")
        return
    rows = []
    for item in members:
        try:
            uid = int(item["id"])
        except (TypeError, ValueError, KeyError):
            continue
        rows.append((uid, str(item.get("name", "Member")), await economy.balance(uid, _scope(chat_id))))
    ranked = sorted(rows, key=lambda x: x[2], reverse=True)[:10]
    if not ranked:
        await update.message.reply_text("No accounts yet — use /daily to get started!")
        return
    lines = [f"{i+1}. {mention(uid, name)} — {coins} coins" for i, (uid, name, coins) in enumerate(ranked)]
    await update.message.reply_text("💰 *Richest Members*\n\n" + "\n".join(lines), parse_mode="Markdown")
