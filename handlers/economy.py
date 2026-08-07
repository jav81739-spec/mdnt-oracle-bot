"""
Fake economy system tied to group activity — now persisted via
handlers/storage.py (Upstash Redis) so coins survive Render restarts.

If UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN aren't set, this
still works exactly as before, just without persistence (resets on
restart) — nothing breaks either way.
"""
import random
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention
from handlers import storage

# In-memory cache, mirrored to Redis on every write.
# Structure: {"<chat_id>": {"<user_id>": {"name": str, "coins": int, "last_daily": str|None}}}
# All keys are STRINGS so this round-trips through JSON cleanly.
economy = {}

DAILY_AMOUNT = 100
ROB_SUCCESS_CHANCE = 0.4
ROB_STEAL_PERCENT = 0.25
ROB_FAIL_PENALTY = 50

STORAGE_KEY = "economy"


async def load_from_storage():
    """Call once at bot startup to restore balances from Redis."""
    global economy
    economy = await storage.load(STORAGE_KEY, {})


async def _persist():
    await storage.save(STORAGE_KEY, economy)


def _get_account(chat_id: int, user_id: int, name: str):
    cid, uid = str(chat_id), str(user_id)
    economy.setdefault(cid, {})
    if uid not in economy[cid]:
        economy[cid][uid] = {"name": name, "coins": 0, "last_daily": None}
    return economy[cid][uid]


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    account = _get_account(chat_id, user.id, user.first_name)
    today = str(datetime.date.today())

    if account["last_daily"] == today:
        await update.message.reply_text("⏳ You already claimed today's coins — come back tomorrow!")
        return

    account["coins"] += DAILY_AMOUNT
    account["last_daily"] = today
    await _persist()
    await update.message.reply_text(f"💰 +{DAILY_AMOUNT} coins claimed! Balance: {account['coins']}")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    account = _get_account(chat_id, target.id, target.first_name)
    await update.message.reply_text(
        f"💰 {mention(target.id, target.first_name)}'s balance: *{account['coins']}* coins",
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

    robber_account = _get_account(chat_id, robber.id, robber.first_name)
    victim_account = _get_account(chat_id, victim.id, victim.first_name)

    if victim_account["coins"] < 20:
        await update.message.reply_text(f"{victim.first_name} is too broke to rob 💀")
        return

    if random.random() < ROB_SUCCESS_CHANCE:
        stolen = int(victim_account["coins"] * ROB_STEAL_PERCENT)
        victim_account["coins"] -= stolen
        robber_account["coins"] += stolen
        await _persist()
        await update.message.reply_text(
            f"🥷 {mention(robber.id, robber.first_name)} successfully robbed "
            f"{stolen} coins from {mention(victim.id, victim.first_name)}!",
            parse_mode="Markdown",
        )
    else:
        robber_account["coins"] = max(0, robber_account["coins"] - ROB_FAIL_PENALTY)
        await _persist()
        await update.message.reply_text(
            f"🚨 {mention(robber.id, robber.first_name)} got caught robbing "
            f"{mention(victim.id, victim.first_name)} and paid a {ROB_FAIL_PENALTY} coin fine!",
            parse_mode="Markdown",
        )


async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    account = _get_account(chat_id, user.id, user.first_name)

    if not context.args:
        await update.message.reply_text("Usage: /gamble [amount]")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Enter a valid number")
        return
    if amount <= 0 or amount > account["coins"]:
        await update.message.reply_text(f"You only have {account['coins']} coins")
        return

    if random.random() < 0.5:
        account["coins"] += amount
        await _persist()
        await update.message.reply_text(f"🎰 You won! +{amount} coins. Balance: {account['coins']}")
    else:
        account["coins"] -= amount
        await _persist()
        await update.message.reply_text(f"💸 You lost {amount} coins. Balance: {account['coins']}")


async def economy_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    accounts = economy.get(str(chat_id), {})
    if not accounts:
        await update.message.reply_text("No accounts yet — use /daily to get started!")
        return
    ranked = sorted(accounts.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]
    lines = [f"{i+1}. {mention(int(uid), data['name'])} — {data['coins']} coins" for i, (uid, data) in enumerate(ranked)]
    await update.message.reply_text("💰 *Richest Members*\n\n" + "\n".join(lines), parse_mode="Markdown")
