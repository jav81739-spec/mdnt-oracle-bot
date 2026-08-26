"""Durable relationship and social-economy commands for Midnight Oracle."""
from __future__ import annotations

import datetime
import json
import random

from telegram import Update
from telegram.ext import ContextTypes

from core.economy import EconomyError, service as economy
from core.storage import storage
from handlers.mentions import mention

STORAGE_KEY = "marriage:v2"
LEGACY_KEY = "marriage"

JOBS = [
    ("barista", 20, 60), ("dog walker", 15, 45), ("streamer", 10, 90),
    ("delivery rider", 25, 55), ("tutor", 30, 70), ("street musician", 5, 80),
]
SHOP_ITEMS = {"ring": 200, "flowers": 50, "chocolate": 30, "teddy bear": 75, "crown": 500}
CHEST_REWARDS = [("coins", 20, 100), ("coins", 100, 300), ("item:flowers", 1, 1), ("item:chocolate", 1, 1), ("nothing", 0, 0)]


def _fresh() -> dict:
    return {"chats": {}}


def _chat(state: dict, chat_id: int) -> dict:
    chats = state.setdefault("chats", {})
    return chats.setdefault(str(chat_id), {
        "marriages": {}, "proposals": {}, "inventory": {},
        "last_work": {}, "last_chest": {}, "settings": {"require_accept": True},
        "names": {},
    })


async def load_from_storage() -> None:
    """Load and migrate the old single JSON blob once at startup."""
    if await storage.exists(STORAGE_KEY):
        return
    async with storage.lock("marriage-migration", ttl=30, wait=1) as acquired:
        if not acquired or await storage.exists(STORAGE_KEY):
            return
        legacy = await storage.load(LEGACY_KEY, {})
        if isinstance(legacy, dict) and legacy:
            await storage.save(STORAGE_KEY, {"chats": legacy})
        else:
            await storage.save(STORAGE_KEY, _fresh())


async def _load() -> dict:
    state = await storage.load(STORAGE_KEY, _fresh())
    return state if isinstance(state, dict) else _fresh()


async def _save(state: dict) -> None:
    await storage.save(STORAGE_KEY, state)


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in {"administrator", "creator"}


async def marry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /marry to propose 💍")
        return
    proposer, target = update.effective_user, update.message.reply_to_message.from_user
    if target.id == proposer.id or target.is_bot:
        await update.message.reply_text("That proposal isn't available 😅")
        return
    cid, pid, tid = update.effective_chat.id, str(proposer.id), str(target.id)
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Relationship state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        chat["names"].update({pid: proposer.first_name, tid: target.first_name})
        if pid in chat["marriages"]:
            await update.message.reply_text("You're already married! Use /divorce first.")
            return
        if tid in chat["marriages"]:
            await update.message.reply_text(f"{target.first_name} is already married 💔")
            return
        if not chat["settings"].get("require_accept", True):
            chat["marriages"][pid] = tid
            chat["marriages"][tid] = pid
            chat["proposals"].pop(tid, None)
            await _save(state)
            text = f"💍 {mention(proposer.id, proposer.first_name)} and {mention(target.id, target.first_name)} are now married!"
        else:
            chat["proposals"][tid] = pid
            await _save(state)
            text = f"💍 {mention(proposer.id, proposer.first_name)} proposed to {mention(target.id, target.first_name)}! They can type /accept."
    await update.message.reply_text(text, parse_mode="Markdown")


async def accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Relationship state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        proposer = chat["proposals"].get(uid)
        if not proposer:
            await update.message.reply_text("You don't have a pending proposal to accept.")
            return
        if proposer in chat["marriages"] or uid in chat["marriages"]:
            chat["proposals"].pop(uid, None)
            await _save(state)
            await update.message.reply_text("That proposal is no longer available.")
            return
        chat["names"][uid] = user.first_name
        chat["marriages"][uid] = proposer
        chat["marriages"][proposer] = uid
        del chat["proposals"][uid]
        await _save(state)
    await update.message.reply_text(f"💒 {mention(user.id, user.first_name)} accepted! Congrats 🎉", parse_mode="Markdown")


async def divorce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Relationship state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        partner = chat["marriages"].get(uid)
        if not partner:
            await update.message.reply_text("You're not married right now.")
            return
        chat["marriages"].pop(uid, None)
        chat["marriages"].pop(partner, None)
        await _save(state)
    await update.message.reply_text(f"💔 {mention(user.id, user.first_name)} is now divorced.", parse_mode="Markdown")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    cid = update.effective_chat.id
    state = await _load()
    chat = _chat(state, cid)
    uid = str(target.id)
    partner = chat["marriages"].get(uid)
    partner_name = chat["names"].get(str(partner), "Someone") if partner else None
    items = chat["inventory"].get(uid, {})
    coins = await economy.balance(target.id, str(cid))
    status = f"Married to {mention(int(partner), partner_name)}" if partner else "Single"
    items_line = ", ".join(f"{k} x{v}" for k, v in items.items()) or "Empty"
    await update.message.reply_text(
        f"👤 *Profile: {target.first_name}*\n\n💰 Coins: {coins}\n💍 Status: {status}\n🎒 Inventory: {items_line}",
        parse_mode="Markdown",
    )


async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    today = datetime.date.today().isoformat()
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Social state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        if chat["last_work"].get(uid) == today:
            await update.message.reply_text("⏳ You already worked today — come back tomorrow!")
            return
        job, lo, hi = random.choice(JOBS)
        earned = random.randint(lo, hi)
        try:
            tx = await economy.add(user.id, earned, "work", scope=str(cid))
        except EconomyError as exc:
            await update.message.reply_text(f"⏳ Couldn't complete work safely: {exc}")
            return
        chat["last_work"][uid] = today
        chat["names"][uid] = user.first_name
        await _save(state)
    await update.message.reply_text(f"🛠️ You worked as a {job} and earned {earned} coins! Balance: {tx.balance}")


async def chests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    today = datetime.date.today().isoformat()
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Social state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        if chat["last_chest"].get(uid) == today:
            await update.message.reply_text("🎁 You already opened today's chest — come back tomorrow!")
            return
        reward_type, lo, hi = random.choice(CHEST_REWARDS)
        reward_text = "nothing"
        if reward_type == "coins":
            amount = random.randint(lo, hi)
            try:
                tx = await economy.add(user.id, amount, "chest", scope=str(cid))
            except EconomyError as exc:
                await update.message.reply_text(f"⏳ Chest couldn't be committed safely: {exc}")
                return
            reward_text = f"{amount} coins (balance {tx.balance})"
        elif reward_type.startswith("item:"):
            item = reward_type.split(":", 1)[1]
            inv = chat["inventory"].setdefault(uid, {})
            inv[item] = int(inv.get(item, 0)) + 1
            reward_text = f"a {item}"
        chat["last_chest"][uid] = today
        await _save(state)
    await update.message.reply_text(f"🎁 You opened a chest and found {reward_text}!")


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"{name} — {price} coins" for name, price in SHOP_ITEMS.items()]
    await update.message.reply_text("🛒 *Shop*\n\n" + "\n".join(lines) + "\n\nBuy with /buy <item name>", parse_mode="Markdown")


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /buy <item name>")
        return
    item = " ".join(context.args).lower()
    if item not in SHOP_ITEMS:
        await update.message.reply_text("That item isn't in the shop. Check /shop.")
        return
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Shop state is busy — try again.")
            return
        state, chat = await _load(), None
        chat = _chat(state, cid)
        try:
            tx = await economy.remove(user.id, SHOP_ITEMS[item], "shop", scope=str(cid))
        except EconomyError:
            await update.message.reply_text(f"You need {SHOP_ITEMS[item]} coins for {item}.")
            return
        inv = chat["inventory"].setdefault(uid, {})
        inv[item] = int(inv.get(item, 0)) + 1
        await _save(state)
    await update.message.reply_text(f"✅ Bought {item} for {SHOP_ITEMS[item]} coins! Balance: {tx.balance}")


async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat = _chat(await _load(), update.effective_chat.id)
    items = chat["inventory"].get(str(target.id), {})
    if not items:
        await update.message.reply_text(f"{target.first_name}'s inventory is empty.")
        return
    await update.message.reply_text(f"🎒 *{target.first_name}'s Inventory*\n\n" + "\n".join(f"{k} x{v}" for k, v in items.items()), parse_mode="Markdown")


async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to someone with /gift <amount>")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Enter a valid number")
        return
    if amount <= 0:
        await update.message.reply_text("Amount must be positive")
        return
    sender, recipient = update.effective_user, update.message.reply_to_message.from_user
    if sender.id == recipient.id:
        await update.message.reply_text("You can't gift yourself 😅")
        return
    try:
        txs = await economy.transfer(sender.id, recipient.id, amount, "gift", scope=str(update.effective_chat.id))
    except EconomyError as exc:
        await update.message.reply_text(f"⏳ Gift couldn't be committed safely: {exc}")
        return
    await update.message.reply_text(
        f"🎁 {mention(sender.id, sender.first_name)} gifted {amount} coins to {mention(recipient.id, recipient.first_name)}!",
        parse_mode="Markdown",
    )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    state = await _load()
    chat = _chat(state, cid)
    if not context.args:
        current = bool(chat["settings"].get("require_accept", True))
        await update.message.reply_text(f"⚙️ Marriage requires /accept: {'ON' if current else 'OFF'}\nToggle with /settings marry_accept")
        return
    if context.args[0].lower() != "marry_accept":
        await update.message.reply_text("Unknown setting. Available: marry_accept")
        return
    if not await _is_admin(update, context):
        await update.message.reply_text("Only group admins can change marriage settings.")
        return
    async with storage.lock(f"marriage:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ Settings are busy — try again.")
            return
        state = await _load()
        chat = _chat(state, cid)
        current = bool(chat["settings"].get("require_accept", True))
        chat["settings"]["require_accept"] = not current
        await _save(state)
    await update.message.reply_text(f"⚙️ Marriage now {'requires' if not current else 'no longer requires'} /accept in this chat.")
