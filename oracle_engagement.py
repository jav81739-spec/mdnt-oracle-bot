"""
engagement.py — Daily Check-in, Streaks, Gift, Rob, Vent, Leaderboard
Midnight Oracle Bot | Persistent via Upstash Redis
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import asyncio
from datetime import datetime, date, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from redis_client import redis_client

# ─── Coins helpers (reuse your existing pattern) ───────────────────────────
async def get_coins(user_id: int) -> int:
    val = await redis_client.get(f"coins:{user_id}")
    return int(val) if val else 0

async def set_coins(user_id: int, amount: int):
    await redis_client.set(f"coins:{user_id}", str(max(0, amount)))

async def add_coins(user_id: int, amount: int):
    current = await get_coins(user_id)
    await set_coins(user_id, current + amount)

# ─── Streak helpers ────────────────────────────────────────────────────────
async def get_streak(user_id: int) -> int:
    val = await redis_client.get(f"streak:{user_id}")
    return int(val) if val else 0

async def get_last_checkin(user_id: int) -> str | None:
    return await redis_client.get(f"checkin_date:{user_id}")

async def set_streak(user_id: int, streak: int):
    await redis_client.set(f"streak:{user_id}", str(streak))

async def set_last_checkin(user_id: int, date_str: str):
    await redis_client.set(f"checkin_date:{user_id}", date_str)

# ─── /checkin ──────────────────────────────────────────────────────────────
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    last = await get_last_checkin(user.id)
    streak = await get_streak(user.id)

    if last == today:
        await update.message.reply_text(
            f"🌙 *You've already checked in today, {user.first_name}.*\n"
            f"Come back tomorrow to keep your streak alive ✨\n"
            f"Current streak: `{streak}` days",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Update streak
    if last == yesterday:
        streak += 1
    else:
        streak = 1  # reset

    await set_streak(user.id, streak)
    await set_last_checkin(user.id, today)

    # Coin reward with streak multiplier
    base_reward = 100
    if streak >= 30:
        multiplier = 5.0
        tier = "🔱 LEGENDARY"
    elif streak >= 14:
        multiplier = 3.0
        tier = "💎 EPIC"
    elif streak >= 7:
        multiplier = 2.0
        tier = "🔥 ON FIRE"
    elif streak >= 3:
        multiplier = 1.5
        tier = "⚡ BUILDING"
    else:
        multiplier = 1.0
        tier = "🌱 FRESH"

    reward = int(base_reward * multiplier)
    await add_coins(user.id, reward)
    total = await get_coins(user.id)

    # Streak flavor text
    streak_msgs = {
        1: "A new journey begins...",
        3: "Three days strong 🌑",
        7: "A week in the Oracle's grace 🌙",
        14: "Two weeks — the shadows know your name 🖤",
        30: "THIRTY DAYS. You are the Oracle's chosen 🔱",
        100: "100 DAYS. Become legend. 🌌"
    }
    flavor = streak_msgs.get(streak, f"Day {streak} — the ritual continues")

    oracle_whispers = [
        "The stars aligned just for you tonight.",
        "Something stirs in the cosmic depths...",
        "The Oracle smiles upon your devotion.",
        "Consistency is its own kind of magic.",
        "The midnight hour rewards the faithful.",
    ]

    await update.message.reply_text(
        f"🌙 *CHECK-IN SUCCESSFUL*\n\n"
        f"_{flavor}_\n\n"
        f"👤 {user.first_name}\n"
        f"🔥 Streak: `{streak}` days  |  {tier}\n"
        f"✨ Multiplier: `{multiplier}x`\n"
        f"🪙 Earned: `+{reward}` coins\n"
        f"💰 Balance: `{total}` coins\n\n"
        f"_{random.choice(oracle_whispers)}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /gift ─────────────────────────────────────────────────────────────────
async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.message.reply_to_message:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "💝 *Gift coins to someone!*\n\n"
                "Usage: Reply to their message with `/gift <amount>`\n"
                "Or: `/gift @username <amount>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    # Parse target and amount
    target = None
    amount = 0

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        try:
            amount = int(context.args[0]) if context.args else 0
        except (ValueError, IndexError):
            amount = 0
    else:
        try:
            amount = int(context.args[-1])
        except ValueError:
            await update.message.reply_text("❌ Please specify a valid coin amount.")
            return

    if not target:
        await update.message.reply_text("❌ Reply to someone's message to gift them coins!")
        return

    if target.id == user.id:
        await update.message.reply_text("😅 You can't gift coins to yourself, bestie.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than 0.")
        return

    sender_coins = await get_coins(user.id)
    if sender_coins < amount:
        await update.message.reply_text(
            f"💸 You only have `{sender_coins}` coins. Not enough to gift `{amount}`!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await add_coins(user.id, -amount)
    await add_coins(target.id, amount)

    gift_msgs = [
        "A rare act of generosity in the dark 🖤",
        "The Oracle blesses this exchange ✨",
        "Coins flow like moonlight between souls 🌙",
        "A true midnight offering 💝",
    ]

    await update.message.reply_text(
        f"💝 *GIFT SENT*\n\n"
        f"From: {user.first_name}\n"
        f"To: {target.first_name}\n"
        f"Amount: `{amount}` 🪙\n\n"
        f"_{random.choice(gift_msgs)}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /rob ──────────────────────────────────────────────────────────────────
ROB_COOLDOWN = 3600  # 1 hour between rob attempts

async def rob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "🦹 *Rob someone's coins!*\n\n"
            "Reply to their message with `/rob` to attempt a heist.\n"
            "⚠️ 40% success rate — fail and you lose coins too!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target = update.message.reply_to_message.from_user

    if target.id == user.id:
        await update.message.reply_text("🤦 You can't rob yourself, criminal mastermind.")
        return

    if target.is_bot:
        await update.message.reply_text("🤖 The Oracle cannot be robbed. Nice try.")
        return

    # Cooldown check
    cooldown_key = f"rob_cooldown:{user.id}"
    last_rob = await redis_client.get(cooldown_key)
    if last_rob:
        elapsed = (datetime.now() - datetime.fromisoformat(last_rob)).total_seconds()
        remaining = int(ROB_COOLDOWN - elapsed)
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            await update.message.reply_text(
                f"⏳ The Oracle sees your greed. Wait `{mins}m {secs}s` before your next heist.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    await redis_client.set(cooldown_key, datetime.now().isoformat())

    target_coins = await get_coins(target.id)
    robber_coins = await get_coins(user.id)

    if target_coins < 50:
        await update.message.reply_text(
            f"💀 {target.first_name} is broke. Even the Oracle pities them.",
        )
        return

    success = random.random() < 0.40  # 40% chance

    if success:
        stolen = random.randint(int(target_coins * 0.1), int(target_coins * 0.25))
        stolen = max(10, stolen)
        await add_coins(target.id, -stolen)
        await add_coins(user.id, stolen)

        heist_lines = [
            "slipped through the shadows undetected 🌑",
            "pulled off the perfect midnight heist 🌙",
            "moved like smoke through the Oracle's realm 💨",
            "has the luck of a cursed soul tonight 🎲",
        ]
        await update.message.reply_text(
            f"🦹 *HEIST SUCCESSFUL*\n\n"
            f"{user.first_name} {random.choice(heist_lines)}\n\n"
            f"💸 Stolen from {target.first_name}: `{stolen}` coins\n"
            f"🪙 Your new balance: `{robber_coins + stolen}` coins",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        penalty = random.randint(int(robber_coins * 0.05), int(robber_coins * 0.15))
        penalty = max(10, min(penalty, robber_coins))
        await add_coins(user.id, -penalty)

        caught_lines = [
            "tripped on their own ego 🤡",
            "was caught by the Oracle's all-seeing eye 👁️",
            "has the stealth of a foghorn in a library 📚",
            "dropped their black mask at the crime scene 🎭",
        ]
        await update.message.reply_text(
            f"🚨 *HEIST FAILED*\n\n"
            f"{user.first_name} {random.choice(caught_lines)}\n\n"
            f"💸 Penalty paid to {target.first_name}: `{penalty}` coins\n"
            f"🪙 Remaining balance: `{max(0, robber_coins - penalty)}` coins",
            parse_mode=ParseMode.MARKDOWN
        )

# ─── /leaderboard ──────────────────────────────────────────────────────────
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Weekly leaderboard based on coins."""
    # Scan all coin keys
    try:
        keys = await redis_client.keys("coins:*")
    except Exception:
        await update.message.reply_text("⚠️ Oracle's ledger is currently unavailable.")
        return

    if not keys:
        await update.message.reply_text("📊 No one has any coins yet. Be the first! `/checkin`")
        return

    leaderboard = []
    for key in keys:
        user_id = int(key.split(":")[1])
        coins = await get_coins(user_id)
        if coins > 0:
            leaderboard.append((user_id, coins))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top10 = leaderboard[:10]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for i, (uid, coins) in enumerate(top10):
        try:
            member = await context.bot.get_chat(uid)
            name = member.first_name or f"User {uid}"
        except Exception:
            name = f"Shadow {uid % 1000}"
        lines.append(f"{medals[i]} `{name}` — {coins} 🪙")

    board_text = "\n".join(lines) if lines else "_No data yet_"

    await update.message.reply_text(
        f"🏆 *MIDNIGHT ORACLE LEADERBOARD*\n"
        f"_{datetime.now().strftime('%d %b %Y')}_\n\n"
        f"{board_text}\n\n"
        f"_Use /checkin daily to climb the ranks ✨_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /vent ─────────────────────────────────────────────────────────────────
VENT_COOLDOWN = 43200  # 12 hours

async def vent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anonymous vent — posts to group without revealing who sent it."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "🫀 *The Oracle hears your silence.*\n\n"
            "Type `/vent <your message>` to share anonymously with the group.\n"
            "_No one will know it's you. The Oracle protects its own._",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Cooldown
    cooldown_key = f"vent_cooldown:{user.id}"
    last_vent = await redis_client.get(cooldown_key)
    if last_vent:
        elapsed = (datetime.now() - datetime.fromisoformat(last_vent)).total_seconds()
        remaining = int(VENT_COOLDOWN - elapsed)
        if remaining > 0:
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            await update.message.reply_text(
                f"🌑 The Oracle needs silence to process feelings.\n"
                f"Wait `{hrs}h {mins}m` before venting again.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    await redis_client.set(cooldown_key, datetime.now().isoformat())

    vent_text = " ".join(context.args)

    # Delete original message for anonymity
    try:
        await update.message.delete()
    except Exception:
        pass

    vent_openers = [
        "Someone needed to say this...",
        "A voice from the shadows speaks...",
        "The Oracle carries this message forward...",
        "Someone in this group wants you to know...",
        "The night holds this confession...",
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🫀 *ANONYMOUS VENT*\n"
             f"_{random.choice(vent_openers)}_\n\n"
             f"❝ {vent_text} ❞",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /streakcheck ──────────────────────────────────────────────────────────
async def streakcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = user

    streak = await get_streak(target.id)
    last = await get_last_checkin(target.id)
    coins = await get_coins(target.id)

    if not last:
        await update.message.reply_text(
            f"🌑 {target.first_name} hasn't checked in yet. Not a single day.\n"
            f"Tell them `/checkin` exists. Do them a favor."
        )
        return

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if last == today:
        status = "✅ Checked in today"
    elif last == yesterday:
        status = "⚠️ At risk — hasn't checked in today yet"
    else:
        status = "💀 Streak broken (missed check-in)"

    await update.message.reply_text(
        f"📊 *STREAK PROFILE*\n\n"
        f"👤 {target.first_name}\n"
        f"🔥 Streak: `{streak}` days\n"
        f"💰 Coins: `{coins}`\n"
        f"📅 Status: {status}",
        parse_mode=ParseMode.MARKDOWN
    )
