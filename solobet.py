"""
solobet.py — Solo Bet (50/50 Gambling) for Midnight Oracle Bot
Inspired by Nova's bbet feature

FEATURES:
- /bet <amount> or bbet <amount> in group chat (no command slash needed)
- Shorthand: 5+3 = 5 × 10³ = 5000 coins
- Consecutive win streak tracking
- 200 bets/day limit per user
- 3-second cooldown between bets
- 10-minute block if spam detected
- Beautiful win/loss messages with Oracle flavor

USAGE:
  /bet 500          — bet 500 coins
  /bet 5k           — bet 5000 coins  
  /bet 5+3          — bet 5000 coins (base+exponent shorthand)
  bbet 200          — works without the slash too (text trigger)
"""

import random
import asyncio
from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from redis_client import redis_client

# ─── Coin helpers ──────────────────────────────────────────────────────────
async def get_coins(user_id: int) -> int:
    val = await redis_client.get(f"coins:{user_id}")
    return int(val) if val else 0

async def add_coins(user_id: int, amount: int):
    current = await get_coins(user_id)
    new_val = max(0, current + amount)
    await redis_client.set(f"coins:{user_id}", str(new_val))

# ─── Parse bet amount (handles shorthand) ──────────────────────────────────
def parse_bet_amount(raw: str) -> int | None:
    """
    Supports:
      500       → 500
      5k        → 5000
      5K        → 5000
      5+3       → 5 × 10³ = 5000
      5.5k      → 5500
      all / max → -1 (signal to use full balance)
    """
    raw = raw.strip().lower()

    if raw in ("all", "max"):
        return -1  # special flag

    # Base+exponent shorthand: 5+3 = 5000
    if "+" in raw and not raw.startswith("+"):
        parts = raw.split("+")
        if len(parts) == 2:
            try:
                base = float(parts[0])
                exp = int(parts[1])
                return int(base * (10 ** exp))
            except ValueError:
                return None

    # K shorthand
    if raw.endswith("k"):
        try:
            return int(float(raw[:-1]) * 1000)
        except ValueError:
            return None

    # Plain number
    try:
        return int(float(raw))
    except ValueError:
        return None

# ─── Limits & cooldowns ────────────────────────────────────────────────────
DAILY_BET_LIMIT = 200
BET_COOLDOWN_SECONDS = 3
SPAM_BLOCK_SECONDS = 600  # 10 minutes

async def check_daily_limit(user_id: int) -> tuple[bool, int]:
    """Returns (is_over_limit, count_today)"""
    today = date.today().isoformat()
    key = f"bet_count:{user_id}:{today}"
    val = await redis_client.get(key)
    count = int(val) if val else 0
    return count >= DAILY_BET_LIMIT, count

async def increment_bet_count(user_id: int):
    today = date.today().isoformat()
    key = f"bet_count:{user_id}:{today}"
    val = await redis_client.get(key)
    count = int(val) if val else 0
    await redis_client.setex(key, 86400, str(count + 1))

async def check_cooldown(user_id: int) -> tuple[bool, float]:
    """Returns (is_blocked, seconds_remaining)"""
    # Check spam block first
    block_key = f"bet_spamblock:{user_id}"
    blocked = await redis_client.get(block_key)
    if blocked:
        ttl = await redis_client.ttl(block_key)
        return True, ttl

    # Check regular cooldown
    cd_key = f"bet_cooldown:{user_id}"
    last = await redis_client.get(cd_key)
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
        if elapsed < BET_COOLDOWN_SECONDS:
            return False, BET_COOLDOWN_SECONDS - elapsed

    return False, 0.0

async def set_cooldown(user_id: int):
    await redis_client.set(f"bet_cooldown:{user_id}", datetime.now().isoformat())

async def trigger_spam_block(user_id: int):
    await redis_client.setex(f"bet_spamblock:{user_id}", SPAM_BLOCK_SECONDS, "1")

# ─── Streak tracking ────────────────────────────────────────────────────────
async def get_bet_streak(user_id: int) -> int:
    val = await redis_client.get(f"bet_streak:{user_id}")
    return int(val) if val else 0

async def set_bet_streak(user_id: int, streak: int):
    await redis_client.set(f"bet_streak:{user_id}", str(streak))

async def get_bet_stats(user_id: int) -> dict:
    wins = await redis_client.get(f"bet_wins:{user_id}") or "0"
    losses = await redis_client.get(f"bet_losses:{user_id}") or "0"
    biggest_win = await redis_client.get(f"bet_bigwin:{user_id}") or "0"
    return {
        "wins": int(wins),
        "losses": int(losses),
        "biggest_win": int(biggest_win),
    }

async def update_bet_stats(user_id: int, won: bool, amount: int):
    if won:
        wins = int(await redis_client.get(f"bet_wins:{user_id}") or "0") + 1
        await redis_client.set(f"bet_wins:{user_id}", str(wins))
        biggest = int(await redis_client.get(f"bet_bigwin:{user_id}") or "0")
        if amount > biggest:
            await redis_client.set(f"bet_bigwin:{user_id}", str(amount))
    else:
        losses = int(await redis_client.get(f"bet_losses:{user_id}") or "0") + 1
        await redis_client.set(f"bet_losses:{user_id}", str(losses))

# ─── Win/loss flavor text ──────────────────────────────────────────────────
WIN_MESSAGES = [
    "🌙 *THE ORACLE SMILED UPON YOU*",
    "✨ *FORTUNE FAVORS THE FAITHFUL*",
    "💰 *MIDNIGHT LUCK IS REAL*",
    "🔱 *THE STARS ALIGNED*",
    "🃏 *THE ORACLE DEALT YOU A GOOD HAND*",
    "⚡ *CHAOS CHOSE YOUR SIDE TONIGHT*",
    "🖤 *THE VOID GAVE BACK*",
    "🌌 *COSMIC LUCK — IT EXISTS*",
]

LOSS_MESSAGES = [
    "💀 *THE ORACLE TAKES WHAT IS OWED*",
    "🌑 *THE DARKNESS CONSUMED YOUR BET*",
    "😭 *EVEN THE STARS MAKE MISTAKES*",
    "🃏 *THE ORACLE FOLDED YOUR FATE*",
    "🌊 *THE VOID CLAIMED YOUR COINS*",
    "💸 *MIDNIGHT IS NOT ALWAYS KIND*",
    "🖤 *THE SHADOW WINS THIS ROUND*",
    "⚰️ *REST IN PEACE, DEAR COINS*",
]

WIN_FLAVORS = [
    "someday this luck will run out. not today though 😌",
    "the oracle is watching. spend wisely 🌙",
    "chaotic good. absolutely chaotic good.",
    "you felt that one in your soul, didn't you ✨",
    "the night rewards the bold 🖤",
]

LOSS_FLAVORS = [
    "the oracle said nothing. it just watched. 👁️",
    "that's a emotion.",
    "next time, maybe 🌑",
    "50/50. the cruelest odds. 😭",
    "the void is full of your coins now 💀",
]

STREAK_COMMENTS = {
    2:  "🔥 2 in a row!",
    3:  "🔥🔥 Hat trick!",
    5:  "⚡ 5-WIN STREAK — you're scaring the oracle",
    7:  "🌙 7 wins. Lucky number energy.",
    10: "💀 10-WIN STREAK. UNREAL.",
    15: "🔱 15 WINS IN A ROW. THE ORACLE BOWS.",
    20: "🌌 20 STREAK. YOU HAVE DEFEATED FATE ITSELF.",
}

# ─── Core bet logic ────────────────────────────────────────────────────────
async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_amount: str):
    user = update.effective_user
    message = update.message

    # Check spam block / cooldown
    is_blocked, remaining = await check_cooldown(user.id)
    if is_blocked and remaining > SPAM_BLOCK_SECONDS - 5:
        # Full spam block
        mins = int(remaining) // 60
        secs = int(remaining) % 60
        await message.reply_text(
            f"🚫 You've been blocked for spamming bets.\n"
            f"Chill for `{mins}m {secs}s` 🌑",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not is_blocked and remaining > 0:
        # Regular cooldown — track rapid attempts
        spam_attempt_key = f"bet_rapidfire:{user.id}"
        rapid = await redis_client.get(spam_attempt_key)
        rapid_count = int(rapid) + 1 if rapid else 1
        await redis_client.setex(spam_attempt_key, 10, str(rapid_count))

        if rapid_count >= 3:
            await trigger_spam_block(user.id)
            await message.reply_text(
                f"🚫 Spam detected. You're blocked from betting for `10 minutes`.\n"
                f"The Oracle does not tolerate chaos. 🌑",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await message.reply_text(
            f"⏳ Wait `{remaining:.1f}s` between bets.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Daily limit check
    over_limit, count = await check_daily_limit(user.id)
    if over_limit:
        await message.reply_text(
            f"📊 You've hit the daily bet limit of `{DAILY_BET_LIMIT}` bets.\n"
            f"Come back tomorrow 🌙",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse amount
    amount = parse_bet_amount(raw_amount)
    if amount is None:
        await message.reply_text(
            "❌ Invalid bet amount.\n"
            "Try: `bbet 500` | `bbet 5k` | `bbet 5+3` | `bbet all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    balance = await get_coins(user.id)

    # Handle "all"
    if amount == -1:
        amount = balance

    if amount <= 0:
        await message.reply_text("❌ Bet must be greater than 0.")
        return

    if amount < 5:
        await message.reply_text("❌ Minimum bet is 5 coins.")
        return

    if amount > 100000:
        await message.reply_text("❌ Maximum single bet is 100,000 coins.")
        return

    if balance < amount:
        await message.reply_text(
            f"💸 Not enough coins!\n"
            f"Balance: `{balance}` | Bet: `{amount}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Set cooldown before resolving
    await set_cooldown(user.id)
    await increment_bet_count(user.id)

    # Flip the coin — 50/50
    won = random.random() < 0.50

    # Update coins
    if won:
        await add_coins(user.id, amount)  # win = +bet
        new_balance = balance + amount
    else:
        await add_coins(user.id, -amount)  # loss = -bet
        new_balance = max(0, balance - amount)

    # Update streaks
    streak = await get_bet_streak(user.id)
    if won:
        streak += 1
    else:
        streak = 0
    await set_bet_streak(user.id, streak)
    await update_bet_stats(user.id, won, amount)

    # Build response
    if won:
        header = random.choice(WIN_MESSAGES)
        flavor = random.choice(WIN_FLAVORS)
        result_line = f"📈 Won: `+{amount}` coins"
        balance_emoji = "💰"
    else:
        header = random.choice(LOSS_MESSAGES)
        flavor = random.choice(LOSS_FLAVORS)
        result_line = f"📉 Lost: `-{amount}` coins"
        balance_emoji = "💸"

    # Streak commentary
    streak_line = ""
    if won and streak >= 2:
        for threshold in sorted(STREAK_COMMENTS.keys(), reverse=True):
            if streak >= threshold:
                streak_line = f"\n{STREAK_COMMENTS[threshold]}"
                break

    # Format bet for display
    if amount >= 1000:
        bet_display = f"{amount:,}"
    else:
        bet_display = str(amount)

    response = (
        f"{header}\n\n"
        f"👤 {user.first_name}\n"
        f"🎲 Bet: `{bet_display}` coins\n"
        f"{result_line}\n"
        f"{balance_emoji} Balance: `{new_balance:,}` coins"
    )

    if streak >= 2 and won:
        response += f"\n🔥 Win streak: `{streak}`{streak_line}"

    response += f"\n\n_{flavor}_"

    # Remaining bets today
    remaining_bets = DAILY_BET_LIMIT - (count + 1)
    if remaining_bets <= 20:
        response += f"\n⚠️ _Only {remaining_bets} bets left today_"

    await message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# ─── /bet command ──────────────────────────────────────────────────────────
async def bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        user = update.effective_user
        stats = await get_bet_stats(user.id)
        streak = await get_bet_streak(user.id)
        balance = await get_coins(user.id)
        _, count = await check_daily_limit(user.id)

        await update.message.reply_text(
            f"🎲 *SOLO BET — 50/50*\n\n"
            f"Usage: `/bet <amount>`\n\n"
            f"Shorthand:\n"
            f"  `1k` = 1,000\n"
            f"  `5+3` = 5,000 _(base × 10^exp)_\n"
            f"  `all` = full balance\n\n"
            f"📊 *Your Stats:*\n"
            f"💰 Balance: `{balance:,}`\n"
            f"✅ Wins: `{stats['wins']}` | ❌ Losses: `{stats['losses']}`\n"
            f"🔥 Current streak: `{streak}`\n"
            f"🏆 Biggest win: `{stats['biggest_win']:,}`\n"
            f"📅 Bets today: `{count}/{DAILY_BET_LIMIT}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await process_bet(update, context, context.args[0])

# ─── /betstats command ─────────────────────────────────────────────────────
async def betstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = user

    stats = await get_bet_stats(target.id)
    streak = await get_bet_streak(target.id)
    balance = await get_coins(target.id)
    _, count = await check_daily_limit(target.id)

    total = stats["wins"] + stats["losses"]
    win_rate = round((stats["wins"] / total * 100), 1) if total > 0 else 0.0

    await update.message.reply_text(
        f"📊 *BET STATS — {target.first_name}*\n\n"
        f"💰 Balance: `{balance:,}` coins\n"
        f"✅ Wins: `{stats['wins']}`\n"
        f"❌ Losses: `{stats['losses']}`\n"
        f"📈 Win Rate: `{win_rate}%`\n"
        f"🔥 Current Streak: `{streak}`\n"
        f"🏆 Biggest Win: `{stats['biggest_win']:,}`\n"
        f"📅 Bets Today: `{count}/{DAILY_BET_LIMIT}`",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /topbet leaderboard ───────────────────────────────────────────────────
async def topbet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top bettors by total wins."""
    try:
        keys = await redis_client.keys("bet_wins:*")
    except Exception:
        await update.message.reply_text("⚠️ Leaderboard unavailable right now.")
        return

    if not keys:
        await update.message.reply_text("No bets placed yet. Be the first! `/bet`")
        return

    leaderboard = []
    for key in keys:
        uid = int(key.split(":")[1])
        wins = int(await redis_client.get(key) or 0)
        if wins > 0:
            leaderboard.append((uid, wins))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top10 = leaderboard[:10]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for i, (uid, wins) in enumerate(top10):
        try:
            member = await context.bot.get_chat(uid)
            name = member.first_name or "???"
        except Exception:
            name = "Shadow"
        lines.append(f"{medals[i]} `{name}` — {wins} wins")

    board = "\n".join(lines)

    await update.message.reply_text(
        f"🎲 *TOP BETTORS*\n\n"
        f"{board}\n\n"
        f"_Use `/bet <amount>` to join the ranks 🌙_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── "bbet" text trigger (no slash needed) ─────────────────────────────────
async def bbet_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Detects messages starting with 'bbet' in group chats.
    Works without a / prefix, just like Nova's implementation.
    """
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip().lower()
    if not text.startswith("bbet"):
        return

    parts = text.split()
    if len(parts) < 2:
        await message.reply_text(
            "🎲 Usage: `bbet <amount>` or `bbet 5+3` or `bbet all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await process_bet(update, context, parts[1])

def get_bbet_handler():
    """
    Returns MessageHandler for 'bbet' text trigger.
    Register in main.py BEFORE the general AI chat handler:
    
    from solobet import bet_command, betstats_command, topbet_command, get_bbet_handler
    app.add_handler(CommandHandler("bet", bet_command))
    app.add_handler(CommandHandler("betstats", betstats_command))
    app.add_handler(CommandHandler("topbet", topbet_command))
    app.add_handler(get_bbet_handler(), group=0)
    """
    return MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^[Bb][Bb][Ee][Tt]\s+\S+"),
        bbet_text_handler
    )
