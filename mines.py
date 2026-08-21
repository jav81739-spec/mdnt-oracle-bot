"""
mines.py — Mines Game for Midnight Oracle Bot
Inspired by Nova's Mines feature

HOW IT WORKS:
- Player bets coins, picks a difficulty (mines count)
- A hidden grid has gems 💎 and mines 💣
- Every gem revealed increases the multiplier
- Cash out anytime to claim winnings
- Hit a mine = lose your bet

COMMANDS:
/mines <bet> <difficulty>  — Start a mines game
  Difficulty: easy (3 mines), medium (5), hard (8), insane (12)
  Example: /mines 200 medium

Players interact via inline buttons to reveal tiles or cash out.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from redis_client import redis_client

# ─── Coin helpers ──────────────────────────────────────────────────────────
async def get_coins(user_id: int) -> int:
    val = await redis_client.get(f"coins:{user_id}")
    return int(val) if val else 0

async def set_coins(user_id: int, amount: int):
    await redis_client.set(f"coins:{user_id}", str(max(0, amount)))

async def add_coins(user_id: int, amount: int):
    current = await get_coins(user_id)
    await set_coins(user_id, current + amount)

# ─── Difficulty settings ────────────────────────────────────────────────────
DIFFICULTIES = {
    "easy":   {"mines": 3,  "label": "Easy 🌿",    "grid": 16},  # 4x4
    "medium": {"mines": 5,  "label": "Medium ⚡",   "grid": 16},
    "hard":   {"mines": 8,  "label": "Hard 🔥",     "grid": 16},
    "insane": {"mines": 12, "label": "Insane 💀",   "grid": 16},
}

GRID_SIZE = 4  # 4x4 = 16 tiles

# ─── Multiplier table (gems revealed → multiplier) ─────────────────────────
# More mines = higher multiplier per gem
def calculate_multiplier(gems_found: int, mines: int) -> float:
    """
    Fair multiplier: starts at 1.0, grows based on probability.
    Each safe pick increases multiplier by risk factor.
    """
    if gems_found == 0:
        return 1.0
    
    total = GRID_SIZE  # 16 tiles
    safe_tiles = total - mines
    
    multiplier = 1.0
    remaining_safe = safe_tiles
    remaining_total = total
    
    for _ in range(gems_found):
        if remaining_total <= 0 or remaining_safe <= 0:
            break
        # Probability of picking safe = remaining_safe / remaining_total
        # Multiplier increases by inverse of that probability
        risk = remaining_total / remaining_safe
        multiplier *= risk * 0.97  # 3% house edge
        remaining_safe -= 1
        remaining_total -= 1
    
    return round(multiplier, 2)

# ─── Game state management ─────────────────────────────────────────────────
async def save_game(user_id: int, game_data: dict):
    await redis_client.setex(
        f"mines_game:{user_id}",
        600,  # 10 min timeout
        json.dumps(game_data)
    )

async def get_game(user_id: int) -> dict | None:
    data = await redis_client.get(f"mines_game:{user_id}")
    if data:
        return json.loads(data)
    return None

async def delete_game(user_id: int):
    await redis_client.delete(f"mines_game:{user_id}")

# ─── Build the game grid keyboard ──────────────────────────────────────────
def build_grid_keyboard(game: dict, revealed: bool = False) -> InlineKeyboardMarkup:
    grid = game["grid"]          # list of 16: "gem" or "mine"
    revealed_tiles = game["revealed"]  # list of revealed indices
    cashed_out = game.get("cashed_out", False)
    lost = game.get("lost", False)

    rows = []
    for row_idx in range(GRID_SIZE):
        row = []
        for col_idx in range(GRID_SIZE):
            tile_idx = row_idx * GRID_SIZE + col_idx
            
            if tile_idx in revealed_tiles:
                # Show what was there
                tile_type = grid[tile_idx]
                if tile_type == "mine":
                    label = "💣"
                else:
                    label = "💎"
            elif revealed or cashed_out or lost:
                # Game over — reveal everything
                tile_type = grid[tile_idx]
                if tile_type == "mine":
                    label = "💣"
                else:
                    label = "·"  # unrevealed safe tile
            else:
                label = "⬛"
            
            # Only clickable if game is active and tile not revealed
            if tile_idx in revealed_tiles or cashed_out or lost:
                callback = f"mines_noop:{tile_idx}"
            else:
                callback = f"mines_pick:{tile_idx}"
            
            row.append(InlineKeyboardButton(label, callback_data=callback))
        rows.append(row)
    
    # Cash out button (only if game active and at least 1 gem found)
    if not cashed_out and not lost and len(revealed_tiles) > 0:
        multiplier = calculate_multiplier(len(revealed_tiles), game["mines"])
        winnings = int(game["bet"] * multiplier)
        rows.append([
            InlineKeyboardButton(
                f"💰 Cash Out — {winnings} coins ({multiplier}x)",
                callback_data="mines_cashout"
            )
        ])
    
    return InlineKeyboardMarkup(rows)

# ─── Game status text ───────────────────────────────────────────────────────
def build_status_text(game: dict) -> str:
    gems = len(game["revealed"])
    mines = game["mines"]
    bet = game["bet"]
    difficulty = game["difficulty"]
    diff_label = DIFFICULTIES[difficulty]["label"]
    multiplier = calculate_multiplier(gems, mines)
    potential = int(bet * multiplier)
    cashed_out = game.get("cashed_out", False)
    lost = game.get("lost", False)
    username = game.get("username", "Player")

    if lost:
        return (
            f"💣 *MINE HIT — GAME OVER*\n\n"
            f"👤 {username}\n"
            f"💰 Bet: `{bet}` coins\n"
            f"💎 Gems found: `{gems}`\n"
            f"📉 Lost: `{bet}` coins\n\n"
            f"_The Oracle warned you about greed..._"
        )
    
    if cashed_out:
        winnings = int(bet * multiplier)
        profit = winnings - bet
        return (
            f"💰 *CASHED OUT!*\n\n"
            f"👤 {username}\n"
            f"💰 Bet: `{bet}` coins\n"
            f"💎 Gems found: `{gems}`\n"
            f"📈 Multiplier: `{multiplier}x`\n"
            f"🏆 Won: `{winnings}` coins *(+{profit})*\n\n"
            f"_Wise. The Oracle approves._ ✨"
        )
    
    return (
        f"💣 *MINES* — {diff_label}\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 {username}\n"
        f"💰 Bet: `{bet}` coins\n"
        f"💎 Gems: `{gems}` found\n"
        f"📈 Multiplier: `{multiplier}x`\n"
        f"💵 Potential: `{potential}` coins\n"
        f"━━━━━━━━━━━━━━\n"
        f"_Pick a tile. Or cash out. Your call._ 🌙"
    )

# ─── /mines command ────────────────────────────────────────────────────────
async def mines_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Check for active game
    existing = await get_game(user.id)
    if existing:
        await update.message.reply_text(
            "⚠️ You already have an active Mines game!\n"
            "Cash out or hit a mine to finish it first.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse args: /mines <bet> [difficulty]
    args = context.args
    if not args:
        diff_list = "\n".join(
            f"  `{k}` — {v['mines']} mines | {v['label']}"
            for k, v in DIFFICULTIES.items()
        )
        await update.message.reply_text(
            f"💣 *MINES GAME*\n\n"
            f"Reveal gems 💎, dodge mines 💣, cash out before you bust!\n\n"
            f"Usage: `/mines <bet> <difficulty>`\n\n"
            f"Difficulties:\n{diff_list}\n\n"
            f"Example: `/mines 500 hard`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse bet
    try:
        bet_str = args[0].lower().replace("k", "000")
        bet = int(bet_str)
    except ValueError:
        await update.message.reply_text("❌ Invalid bet amount. Example: `/mines 500 medium`")
        return

    if bet < 10:
        await update.message.reply_text("❌ Minimum bet is 10 coins.")
        return

    if bet > 50000:
        await update.message.reply_text("❌ Maximum bet is 50,000 coins.")
        return

    # Parse difficulty
    difficulty = "medium"
    if len(args) >= 2:
        diff_input = args[1].lower()
        if diff_input not in DIFFICULTIES:
            await update.message.reply_text(
                f"❌ Unknown difficulty. Choose: `easy`, `medium`, `hard`, `insane`"
            )
            return
        difficulty = diff_input

    # Check balance
    balance = await get_coins(user.id)
    if balance < bet:
        await update.message.reply_text(
            f"💸 Not enough coins!\n"
            f"Your balance: `{balance}` | Bet: `{bet}`\n"
            f"Use `/checkin` to earn more!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Deduct bet
    await add_coins(user.id, -bet)

    # Generate grid
    mines_count = DIFFICULTIES[difficulty]["mines"]
    total_tiles = GRID_SIZE * GRID_SIZE
    grid = ["gem"] * total_tiles
    mine_positions = random.sample(range(total_tiles), mines_count)
    for pos in mine_positions:
        grid[pos] = "mine"

    # Save game state
    game = {
        "user_id": user.id,
        "username": user.first_name,
        "bet": bet,
        "difficulty": difficulty,
        "mines": mines_count,
        "grid": grid,
        "revealed": [],
        "cashed_out": False,
        "lost": False,
        "message_id": None,
        "chat_id": update.effective_chat.id,
    }
    await save_game(user.id, game)

    keyboard = build_grid_keyboard(game)
    status = build_status_text(game)

    msg = await update.message.reply_text(
        status,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    # Save message ID for editing later
    game["message_id"] = msg.message_id
    await save_game(user.id, game)

# ─── Callback handler (tile picks + cashout) ───────────────────────────────
async def mines_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    await query.answer()

    # Load game
    game = await get_game(user.id)
    if not game:
        await query.answer("⏰ Game expired or doesn't exist!", show_alert=True)
        return

    # Prevent other users from interacting
    if game["user_id"] != user.id:
        await query.answer("❌ This isn't your game!", show_alert=True)
        return

    # Ignore noop buttons
    if data == "mines_noop" or data.startswith("mines_noop:"):
        return

    # Cash out
    if data == "mines_cashout":
        gems = len(game["revealed"])
        if gems == 0:
            await query.answer("Pick at least one gem first!", show_alert=True)
            return

        multiplier = calculate_multiplier(gems, game["mines"])
        winnings = int(game["bet"] * multiplier)

        game["cashed_out"] = True
        await save_game(user.id, game)
        await add_coins(user.id, winnings)
        await delete_game(user.id)

        keyboard = build_grid_keyboard(game)
        status = build_status_text(game)

        await query.edit_message_text(
            status,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Pick a tile
    if data.startswith("mines_pick:"):
        tile_idx = int(data.split(":")[1])

        if tile_idx in game["revealed"]:
            return

        tile_type = game["grid"][tile_idx]

        if tile_type == "mine":
            # BOOM
            game["lost"] = True
            game["revealed"].append(tile_idx)
            await save_game(user.id, game)
            await delete_game(user.id)

            # Reveal all tiles on loss
            keyboard = build_grid_keyboard(game, revealed=True)
            status = build_status_text(game)

            await query.edit_message_text(
                status,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )

        else:
            # Safe! Gem found
            game["revealed"].append(tile_idx)
            gems = len(game["revealed"])
            safe_tiles = (GRID_SIZE * GRID_SIZE) - game["mines"]

            # Auto cash-out if all gems revealed
            if gems >= safe_tiles:
                multiplier = calculate_multiplier(gems, game["mines"])
                winnings = int(game["bet"] * multiplier)
                game["cashed_out"] = True
                await add_coins(user.id, winnings)
                await delete_game(user.id)
            else:
                await save_game(user.id, game)

            keyboard = build_grid_keyboard(game)
            status = build_status_text(game)

            await query.edit_message_text(
                status,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )

# ─── Handler registration helper ────────────────────────────────────────────
def get_mines_handlers():
    """
    Returns list of handlers to register in main.py:
    
    from mines import mines_command, get_mines_handlers
    app.add_handler(CommandHandler("mines", mines_command))
    for h in get_mines_handlers():
        app.add_handler(h)
    """
    return [
        CallbackQueryHandler(mines_callback, pattern="^mines_"),
    ]
