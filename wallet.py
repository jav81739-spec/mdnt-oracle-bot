"""
wallet.py — Wallet / Vault + Account Backup System
Midnight Oracle Bot
Inspired by Baka Bot's vault and account recovery features

FEATURES:
- /wallet         — View your wallet (protected coins)
- /deposit <amt>  — Move coins into protected wallet
- /withdraw <amt> — Take coins out of wallet
- /walletstats    — Full wallet breakdown
- /setpass <pass> — Set account backup password
- /changepass <old> <new> — Change password
- /recover <user_id> <pass> — Recover deleted account's coins

Normal coins CAN be robbed.
Wallet coins CANNOT be robbed (protected vault).
Max 30% of total balance can be in wallet (50% with "Vault" upgrade — future premium feature).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hashlib
import json
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from redis_client import redis_client

# ─── Coin helpers ──────────────────────────────────────────────────────────
async def get_coins(user_id: int) -> int:
    val = await redis_client.get(f"coins:{user_id}")
    return int(val) if val else 0

async def set_coins(user_id: int, amount: int):
    await redis_client.set(f"coins:{user_id}", str(max(0, amount)))

async def get_wallet(user_id: int) -> int:
    val = await redis_client.get(f"wallet:{user_id}")
    return int(val) if val else 0

async def set_wallet(user_id: int, amount: int):
    await redis_client.set(f"wallet:{user_id}", str(max(0, amount)))

# ─── Wallet cap ─────────────────────────────────────────────────────────────
WALLET_CAP_PERCENT = 0.30  # 30% of total holdings by default

def get_wallet_cap(total_coins: int, wallet_coins: int) -> int:
    """Max coins that can be stored in wallet."""
    total_holdings = total_coins + wallet_coins
    return int(total_holdings * WALLET_CAP_PERCENT)

# ─── /wallet ───────────────────────────────────────────────────────────────
async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = await get_coins(user.id)
    wallet = await get_wallet(user.id)
    total = coins + wallet
    cap = get_wallet_cap(coins, wallet)
    pct = round((wallet / total * 100), 1) if total > 0 else 0

    wallet_bar_filled = int((wallet / cap * 10)) if cap > 0 else 0
    wallet_bar_filled = min(wallet_bar_filled, 10)
    wallet_bar = "█" * wallet_bar_filled + "░" * (10 - wallet_bar_filled)

    await update.message.reply_text(
        f"🏦 *MIDNIGHT VAULT*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 {user.first_name}\n\n"
        f"💰 Coins (robbable): `{coins:,}`\n"
        f"🔒 Vault (protected): `{wallet:,}`\n"
        f"📊 Total: `{total:,}`\n\n"
        f"🔐 Vault capacity: `{wallet}/{cap}` ({pct}%)\n"
        f"`{wallet_bar}`\n\n"
        f"Use `/deposit <amount>` to protect coins\n"
        f"Use `/withdraw <amount>` to access them\n"
        f"_Vaulted coins cannot be robbed_ 🛡️",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /deposit ──────────────────────────────────────────────────────────────
async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "🔒 *DEPOSIT TO VAULT*\n\n"
            "Usage: `/deposit <amount>` or `/deposit all`\n"
            "Moves coins into your protected vault.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    coins = await get_coins(user.id)
    wallet = await get_wallet(user.id)
    cap = get_wallet_cap(coins, wallet)

    raw = context.args[0].lower()
    if raw == "all":
        # Deposit as much as allowed
        space = cap - wallet
        amount = min(coins, space)
    else:
        try:
            raw = raw.replace("k", "000")
            amount = int(raw)
        except ValueError:
            await update.message.reply_text("❌ Invalid amount.")
            return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive.")
        return

    if amount > coins:
        await update.message.reply_text(
            f"💸 You only have `{coins:,}` coins to deposit.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check cap
    space = cap - wallet
    if space <= 0:
        await update.message.reply_text(
            f"🔐 Vault is full! Max `{cap:,}` coins (30% of total holdings).\n"
            f"Earn more coins to increase your vault capacity.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if amount > space:
        amount = space
        await update.message.reply_text(
            f"⚠️ Can only deposit `{space:,}` more (vault cap). Depositing that instead.",
            parse_mode=ParseMode.MARKDOWN
        )

    await set_coins(user.id, coins - amount)
    await set_wallet(user.id, wallet + amount)

    new_coins = coins - amount
    new_wallet = wallet + amount

    await update.message.reply_text(
        f"🔒 *DEPOSITED TO VAULT*\n\n"
        f"Moved: `{amount:,}` coins\n"
        f"💰 Coins: `{new_coins:,}`\n"
        f"🔐 Vault: `{new_wallet:,}`\n\n"
        f"_Safe from robbers 🛡️_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /withdraw ─────────────────────────────────────────────────────────────
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "🔓 *WITHDRAW FROM VAULT*\n\n"
            "Usage: `/withdraw <amount>` or `/withdraw all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    coins = await get_coins(user.id)
    wallet = await get_wallet(user.id)

    raw = context.args[0].lower()
    if raw == "all":
        amount = wallet
    else:
        try:
            raw = raw.replace("k", "000")
            amount = int(raw)
        except ValueError:
            await update.message.reply_text("❌ Invalid amount.")
            return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive.")
        return

    if amount > wallet:
        await update.message.reply_text(
            f"💸 Vault only has `{wallet:,}` coins.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await set_wallet(user.id, wallet - amount)
    await set_coins(user.id, coins + amount)

    await update.message.reply_text(
        f"🔓 *WITHDRAWN FROM VAULT*\n\n"
        f"Moved: `{amount:,}` coins\n"
        f"💰 Coins: `{coins + amount:,}`\n"
        f"🔐 Vault: `{wallet - amount:,}`",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Password helpers ────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

async def get_stored_password(user_id: int) -> str | None:
    return await redis_client.get(f"account_pass:{user_id}")

async def set_stored_password(user_id: int, hashed: str):
    await redis_client.set(f"account_pass:{user_id}", hashed)

# ─── /setpass ──────────────────────────────────────────────────────────────
async def setpass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Only in DMs for security
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔐 For security, use this command in my DMs only!\n"
            f"[Open DM](tg://resolve?domain={context.bot.username})",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not context.args:
        await update.message.reply_text(
            "🔐 *ACCOUNT BACKUP PASSWORD*\n\n"
            "This password protects your coins, streaks, and stats.\n"
            "If your Telegram account is ever deleted, use `/recover` on a new account.\n\n"
            "Usage: `/setpass <yourpassword>`\n\n"
            "⚠️ _Never share this password with anyone!_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    password = context.args[0]

    if len(password) < 6:
        await update.message.reply_text("❌ Password must be at least 6 characters.")
        return

    if len(password) > 32:
        await update.message.reply_text("❌ Password too long (max 32 characters).")
        return

    existing = await get_stored_password(user.id)
    if existing:
        await update.message.reply_text(
            "⚠️ You already have a password set.\n"
            "Use `/changepass <old> <new>` to change it."
        )
        return

    hashed = hash_password(password)
    await set_stored_password(user.id, hashed)

    # Delete the message so password isn't visible
    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=user.id,
        text=f"✅ *PASSWORD SET SUCCESSFULLY*\n\n"
             f"Your account is now protected.\n"
             f"Store your password somewhere safe.\n\n"
             f"Your User ID: `{user.id}`\n"
             f"_(Save this too — you'll need it for recovery)_\n\n"
             f"⚠️ _The Oracle does not store your actual password — only a hash. If you forget it, it cannot be recovered._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /changepass ───────────────────────────────────────────────────────────
async def changepass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔐 Use this command in DMs only for security!"
        )
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/changepass <old_password> <new_password>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    old_pass = context.args[0]
    new_pass = context.args[1]

    stored = await get_stored_password(user.id)
    if not stored:
        await update.message.reply_text(
            "❌ No password set. Use `/setpass <password>` first."
        )
        return

    if hash_password(old_pass) != stored:
        await update.message.reply_text("❌ Incorrect old password.")
        return

    if len(new_pass) < 6:
        await update.message.reply_text("❌ New password must be at least 6 characters.")
        return

    await set_stored_password(user.id, hash_password(new_pass))

    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=user.id,
        text="✅ Password changed successfully! 🔐"
    )

# ─── /recover ──────────────────────────────────────────────────────────────
async def recover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Transfer coins/stats from a deleted old account to current account.
    Works ONLY if the old account is deleted (Telegram ID no longer exists)
    AND the old account had a password set.
    """
    user = update.effective_user

    if update.effective_chat.type != "private":
        await update.message.reply_text("🔐 Use `/recover` in DMs only!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔐 *ACCOUNT RECOVERY*\n\n"
            "If your old Telegram account was deleted:\n"
            "1. Create a new Telegram account\n"
            "2. Start the bot\n"
            "3. Use: `/recover <old_user_id> <password>`\n\n"
            "You must have set a password on your old account first.\n"
            "_The Oracle transfers: coins, wallet, streaks, stats._",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        old_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    password = context.args[1]

    if old_user_id == user.id:
        await update.message.reply_text("❌ That's your current account ID.")
        return

    # Verify password
    stored = await get_stored_password(old_user_id)
    if not stored:
        await update.message.reply_text(
            "❌ No recovery password found for that account.\n"
            "You must have set `/setpass` before the account was deleted."
        )
        return

    if hash_password(password) != stored:
        await update.message.reply_text("❌ Incorrect password.")
        return

    # Transfer everything
    old_coins = await get_coins(old_user_id)
    old_wallet = await get_wallet(old_user_id)
    old_streak = int(await redis_client.get(f"streak:{old_user_id}") or 0)
    old_bet_wins = int(await redis_client.get(f"bet_wins:{old_user_id}") or 0)
    old_bet_streak = int(await redis_client.get(f"bet_streak:{old_user_id}") or 0)

    # Add to current account
    current_coins = await get_coins(user.id)
    current_wallet = await get_wallet(user.id)

    await set_coins(user.id, current_coins + old_coins)
    await set_wallet(user.id, current_wallet + old_wallet)

    if old_streak > 0:
        await redis_client.set(f"streak:{user.id}", str(old_streak))
    if old_bet_wins > 0:
        curr_wins = int(await redis_client.get(f"bet_wins:{user.id}") or 0)
        await redis_client.set(f"bet_wins:{user.id}", str(curr_wins + old_bet_wins))

    # Wipe old account data
    keys_to_delete = [
        f"coins:{old_user_id}",
        f"wallet:{old_user_id}",
        f"streak:{old_user_id}",
        f"checkin_date:{old_user_id}",
        f"bet_wins:{old_user_id}",
        f"bet_losses:{old_user_id}",
        f"bet_streak:{old_user_id}",
        f"bet_bigwin:{old_user_id}",
        f"account_pass:{old_user_id}",
    ]
    for key in keys_to_delete:
        await redis_client.delete(key)

    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=user.id,
        text=f"✅ *ACCOUNT RECOVERED SUCCESSFULLY*\n\n"
             f"Transferred from account `{old_user_id}`:\n"
             f"💰 Coins: `+{old_coins:,}`\n"
             f"🔐 Vault: `+{old_wallet:,}`\n"
             f"🔥 Streak: `{old_streak}` days\n\n"
             f"_Welcome back. The Oracle remembered you._ 🌙",
        parse_mode=ParseMode.MARKDOWN
    )
