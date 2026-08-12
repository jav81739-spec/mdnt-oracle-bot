"""
Marriage / shop / work / gifting system — built on top of the existing
economy coin balances (handlers/economy.py) and persisted the same way,
via handlers/storage.py (Upstash Redis). If storage isn't configured,
this still works, just resets on restart — same as economy.py.

Commands added:
  /marry (reply)      - propose marriage to the replied user
  /accept             - accept a pending proposal
  /divorce (reply?)   - divorce your partner (or the replied user)
  /profile (reply?)   - view a marriage/coin/inventory profile card
  /work                - earn coins with a random job (separate cooldown from /daily)
  /chests              - open a free daily chest for a random coin/item reward
  /shop                - list items for sale
  /buy <item>          - purchase an item from the shop
  /inventory (reply?)  - view owned items
  /gift <amount> (reply) - send coins to the replied user
  /settings             - toggle whether /marry requires /accept in this chat
"""
import random
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention
from handlers import storage
from handlers import economy

STORAGE_KEY = "marriage"

# Structure:
# {
#   "<chat_id>": {
#     "marriages": {"<uid>": "<partner_uid>", ...},      # symmetric pair, both directions stored
#     "proposals": {"<target_uid>": "<proposer_uid>"},   # pending, one per target
#     "inventory": {"<uid>": {"<item>": qty, ...}},
#     "last_work": {"<uid>": "YYYY-MM-DD"},
#     "last_chest": {"<uid>": "YYYY-MM-DD"},
#     "settings": {"require_accept": True},
#   }
# }
data = {}

JOBS = [
    ("barista", 20, 60),
    ("dog walker", 15, 45),
    ("streamer", 10, 90),
    ("delivery rider", 25, 55),
    ("tutor", 30, 70),
    ("street musician", 5, 80),
]

SHOP_ITEMS = {
    "ring": 200,
    "flowers": 50,
    "chocolate": 30,
    "teddy bear": 75,
    "crown": 500,
}

CHEST_REWARDS = [
    ("coins", 20, 100),
    ("coins", 100, 300),
    ("item:flowers", 1, 1),
    ("item:chocolate", 1, 1),
    ("nothing", 0, 0),
]


async def load_from_storage():
    """Call once at bot startup to restore marriages/inventory/etc from Redis."""
    global data
    data = await storage.load(STORAGE_KEY, {})


async def _persist():
    await storage.save(STORAGE_KEY, data)


def _get_chat(chat_id: int):
    cid = str(chat_id)
    data.setdefault(cid, {
        "marriages": {},
        "proposals": {},
        "inventory": {},
        "last_work": {},
        "last_chest": {},
        "settings": {"require_accept": True},
    })
    chat = data[cid]
    # backfill in case older saved data is missing a key
    for key, default in (
        ("marriages", {}), ("proposals", {}), ("inventory", {}),
        ("last_work", {}), ("last_chest", {}),
        ("settings", {"require_accept": True}),
    ):
        chat.setdefault(key, default)
    return chat


def _partner_of(chat: dict, uid: str):
    return chat["marriages"].get(uid)


async def marry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /marry to propose 💍")
        return

    chat_id = update.effective_chat.id
    proposer = update.effective_user
    target = update.message.reply_to_message.from_user
    chat = _get_chat(chat_id)

    if target.id == proposer.id:
        await update.message.reply_text("You can't marry yourself 😅")
        return
    if target.is_bot:
        await update.message.reply_text("The bot appreciates it, but no 🤖")
        return

    pid, tid = str(proposer.id), str(target.id)

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
        await _persist()
        await update.message.reply_text(
            f"💍 {mention(proposer.id, proposer.first_name)} and "
            f"{mention(target.id, target.first_name)} are now married! (auto-accept is on for this chat)",
            parse_mode="Markdown",
        )
        return

    chat["proposals"][tid] = pid
    await _persist()
    await update.message.reply_text(
        f"💍 {mention(proposer.id, proposer.first_name)} proposed to "
        f"{mention(target.id, target.first_name)}! They can type /accept to say yes.",
        parse_mode="Markdown",
    )


async def accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)

    proposer_id = chat["proposals"].get(uid)
    if not proposer_id:
        await update.message.reply_text("You don't have a pending proposal to accept.")
        return

    chat["marriages"][uid] = proposer_id
    chat["marriages"][proposer_id] = uid
    del chat["proposals"][uid]
    await _persist()
    await update.message.reply_text(
        f"💒 {mention(user.id, user.first_name)} accepted! Congrats to the happy couple 🎉",
        parse_mode="Markdown",
    )


async def divorce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)

    partner_id = _partner_of(chat, uid)
    if not partner_id:
        await update.message.reply_text("You're not married right now.")
        return

    del chat["marriages"][uid]
    del chat["marriages"][partner_id]
    await _persist()
    await update.message.reply_text(f"💔 {mention(user.id, user.first_name)} is now divorced.", parse_mode="Markdown")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    chat = _get_chat(chat_id)
    uid = str(target.id)

    account = economy._get_account(chat_id, target.id, target.first_name)
    partner_id = _partner_of(chat, uid)
    partner_line = "Single"
    if partner_id:
        partner_name = economy.economy.get(str(chat_id), {}).get(partner_id, {}).get("name", "Someone")
        partner_line = f"Married to {mention(int(partner_id), partner_name)}"

    items = chat["inventory"].get(uid, {})
    items_line = ", ".join(f"{k} x{v}" for k, v in items.items()) or "Empty"

    await update.message.reply_text(
        f"👤 *Profile: {target.first_name}*\n\n"
        f"💰 Coins: {account['coins']}\n"
        f"💍 Status: {partner_line}\n"
        f"🎒 Inventory: {items_line}",
        parse_mode="Markdown",
    )


async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)
    today = str(datetime.date.today())

    if chat["last_work"].get(uid) == today:
        await update.message.reply_text("⏳ You already worked today — come back tomorrow!")
        return

    job, lo, hi = random.choice(JOBS)
    earned = random.randint(lo, hi)

    account = economy._get_account(chat_id, user.id, user.first_name)
    account["coins"] += earned
    chat["last_work"][uid] = today
    await economy._persist()
    await _persist()
    await update.message.reply_text(
        f"🛠️ You worked as a {job} and earned {earned} coins! Balance: {account['coins']}"
    )


async def chests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)
    today = str(datetime.date.today())

    if chat["last_chest"].get(uid) == today:
        await update.message.reply_text("🎁 You already opened today's chest — come back tomorrow!")
        return

    chat["last_chest"][uid] = today
    reward_type, lo, hi = random.choice(CHEST_REWARDS)

    if reward_type == "coins":
        amount = random.randint(lo, hi)
        account = economy._get_account(chat_id, user.id, user.first_name)
        account["coins"] += amount
        await economy._persist()
        await _persist()
        await update.message.reply_text(f"🎁 You opened a chest and found {amount} coins!")
    elif reward_type.startswith("item:"):
        item = reward_type.split(":", 1)[1]
        chat["inventory"].setdefault(uid, {})
        chat["inventory"][uid][item] = chat["inventory"][uid].get(item, 0) + 1
        await _persist()
        await update.message.reply_text(f"🎁 You opened a chest and found a {item}!")
    else:
        await _persist()
        await update.message.reply_text("🎁 You opened a chest and found... nothing. Better luck tomorrow!")


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"{name} — {price} coins" for name, price in SHOP_ITEMS.items()]
    await update.message.reply_text("🛒 *Shop*\n\n" + "\n".join(lines) + "\n\nBuy with /buy <item name>", parse_mode="Markdown")


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /buy <item name> — see /shop for options")
        return

    item = " ".join(context.args).lower()
    if item not in SHOP_ITEMS:
        await update.message.reply_text("That item isn't in the shop. Check /shop for the list.")
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)
    price = SHOP_ITEMS[item]

    account = economy._get_account(chat_id, user.id, user.first_name)
    if account["coins"] < price:
        await update.message.reply_text(f"You need {price} coins for {item} — you have {account['coins']}.")
        return

    account["coins"] -= price
    chat["inventory"].setdefault(uid, {})
    chat["inventory"][uid][item] = chat["inventory"][uid].get(item, 0) + 1
    await economy._persist()
    await _persist()
    await update.message.reply_text(f"✅ Bought {item} for {price} coins! Balance: {account['coins']}")


async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    chat = _get_chat(chat_id)
    items = chat["inventory"].get(str(target.id), {})

    if not items:
        await update.message.reply_text(f"{target.first_name}'s inventory is empty.")
        return

    lines = [f"{k} x{v}" for k, v in items.items()]
    await update.message.reply_text(f"🎒 *{target.first_name}'s Inventory*\n\n" + "\n".join(lines), parse_mode="Markdown")


async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /gift <amount> to send them coins")
        return
    if not context.args:
        await update.message.reply_text("Usage: /gift <amount> (as a reply to the recipient)")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Enter a valid number")
        return
    if amount <= 0:
        await update.message.reply_text("Amount must be positive")
        return

    chat_id = update.effective_chat.id
    sender = update.effective_user
    recipient = update.message.reply_to_message.from_user

    if recipient.id == sender.id:
        await update.message.reply_text("You can't gift yourself 😅")
        return

    sender_account = economy._get_account(chat_id, sender.id, sender.first_name)
    if sender_account["coins"] < amount:
        await update.message.reply_text(f"You only have {sender_account['coins']} coins")
        return

    recipient_account = economy._get_account(chat_id, recipient.id, recipient.first_name)
    sender_account["coins"] -= amount
    recipient_account["coins"] += amount
    await economy._persist()
    await update.message.reply_text(
        f"🎁 {mention(sender.id, sender.first_name)} gifted {amount} coins to "
        f"{mention(recipient.id, recipient.first_name)}!",
        parse_mode="Markdown",
    )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat = _get_chat(chat_id)

    if not context.args:
        current = chat["settings"].get("require_accept", True)
        await update.message.reply_text(
            f"⚙️ Marriage requires /accept: {'ON' if current else 'OFF'}\n"
            f"Toggle with /settings marry_accept"
        )
        return

    if context.args[0].lower() == "marry_accept":
        current = chat["settings"].get("require_accept", True)
        chat["settings"]["require_accept"] = not current
        await _persist()
        await update.message.reply_text(
            f"⚙️ Marriage now {'requires' if not current else 'no longer requires'} /accept in this chat."
        )
    else:
        await update.message.reply_text("Unknown setting. Available: marry_accept")
