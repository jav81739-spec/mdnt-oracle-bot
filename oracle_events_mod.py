"""
oracle_events.py — Oracle's Hour & Group Events System
Midnight Oracle Bot

FEATURES:
- /oraclehour    — Admin triggers a group event (first 5 to /enter win coins)
- /enter         — Join an active event
- /eventcheck    — Check if an event is active
- Auto scheduled events via job queue
- Weekly summary auto-post (Sunday)
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from redis_client import redis_client

# ─── Coin helpers (import from engagement or reuse) ────────────────────────
async def get_coins(user_id: int) -> int:
    val = await redis_client.get(f"coins:{user_id}")
    return int(val) if val else 0

async def add_coins(user_id: int, amount: int):
    current = await get_coins(user_id)
    new_val = max(0, current + amount)
    await redis_client.set(f"coins:{user_id}", str(new_val))

# ─── Event types ───────────────────────────────────────────────────────────
EVENT_TYPES = [
    {
        "name": "⚡ THE ORACLE'S RIFT",
        "desc": "A rift has opened in the midnight realm!\nFirst **{slots}** souls to type `/enter` claim the energy.",
        "reward_base": 500,
        "slots": 5,
        "emoji": "⚡"
    },
    {
        "name": "🌙 LUNAR BLESSING",
        "desc": "The moon is full and generous tonight.\nFirst **{slots}** members to `/enter` receive lunar coins.",
        "reward_base": 350,
        "slots": 7,
        "emoji": "🌙"
    },
    {
        "name": "🔮 ORACLE'S GAMBLE",
        "desc": "The Oracle offers a wager.\nFirst **{slots}** to `/enter` get a random reward — high risk, high reward.",
        "reward_base": 0,  # random
        "slots": 5,
        "emoji": "🔮"
    },
    {
        "name": "💀 DEATH MATCH BONUS",
        "desc": "The Death Games echo through the void.\nFirst **{slots}** survivors to `/enter` claim bonus coins.",
        "reward_base": 400,
        "slots": 6,
        "emoji": "💀"
    },
    {
        "name": "🖤 MIDNIGHT OFFERING",
        "desc": "The Oracle accepts offerings at this hour.\nFirst **{slots}** to `/enter` receive the Oracle's blessing.",
        "reward_base": 600,
        "slots": 4,
        "emoji": "🖤"
    },
    {
        "name": "✨ STARDUST SHOWER",
        "desc": "Cosmic stardust rains on the chosen.\nFirst **{slots}** to `/enter` catch the stardust.",
        "reward_base": 300,
        "slots": 8,
        "emoji": "✨"
    },
]

EVENT_DURATION = 120  # seconds (2 minutes to claim)

# ─── /oraclehour ───────────────────────────────────────────────────────────
async def oraclehour_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: trigger a group event."""
    user = update.effective_user
    chat = update.effective_chat

    # Check admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("👁️ Only admins can invoke the Oracle's Hour.")
            return
    except Exception:
        pass

    # Check if event already active
    active = await redis_client.get(f"event_active:{chat.id}")
    if active:
        await update.message.reply_text("⚡ An event is already active! Use `/enter` to join.")
        return

    # Pick random event
    event = random.choice(EVENT_TYPES)
    slots = event["slots"]
    reward_base = event["reward_base"]
    event_key = f"event:{chat.id}"
    entrants_key = f"event_entrants:{chat.id}"

    # Store event data
    await redis_client.setex(f"event_active:{chat.id}", EVENT_DURATION + 30, "1")
    await redis_client.setex(
        event_key,
        EVENT_DURATION + 30,
        f"{event['name']}|{slots}|{reward_base}"
    )
    await redis_client.delete(entrants_key)

    desc = event["desc"].format(slots=slots)

    msg = await update.message.reply_text(
        f"{event['emoji']} *{event['name']}*\n\n"
        f"{desc}\n\n"
        f"⏳ You have **{EVENT_DURATION // 60} minutes** to claim!\n"
        f"🪙 Reward: up to `{reward_base if reward_base else '???'}` coins\n\n"
        f"👇 Type `/enter` NOW!",
        parse_mode=ParseMode.MARKDOWN
    )

    # Schedule event end
    context.job_queue.run_once(
        close_event,
        EVENT_DURATION,
        data={"chat_id": chat.id, "event_name": event["name"], "reward_base": reward_base},
        name=f"event_close_{chat.id}"
    )

# ─── /enter ────────────────────────────────────────────────────────────────
async def enter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    active = await redis_client.get(f"event_active:{chat.id}")
    if not active:
        await update.message.reply_text(
            "🌑 No event is active right now.\nWatch for the Oracle's signal..."
        )
        return

    event_data = await redis_client.get(f"event:{chat.id}")
    if not event_data:
        return

    parts = event_data.split("|")
    event_name = parts[0]
    slots = int(parts[1])
    reward_base = int(parts[2])

    entrants_key = f"event_entrants:{chat.id}"

    # Check if already entered
    existing = await redis_client.lrange(entrants_key, 0, -1)
    if str(user.id) in (existing or []):
        await update.message.reply_text(
            f"👁️ You're already in, {user.first_name}. The Oracle sees your eagerness."
        )
        return

    # Check slot capacity
    current_count = len(existing) if existing else 0
    if current_count >= slots:
        await update.message.reply_text(
            f"💀 Too slow, {user.first_name}. All {slots} spots are taken.\n"
            f"_The void has no more room tonight._"
        )
        return

    # Add entrant
    await redis_client.lpush(entrants_key, str(user.id))
    await redis_client.expire(entrants_key, EVENT_DURATION + 60)

    new_count = current_count + 1
    remaining = slots - new_count

    # Determine reward
    if reward_base == 0:
        reward = random.choice([100, 200, 500, 800, 1200, 50])
    else:
        reward = reward_base + random.randint(-50, 100)

    await add_coins(user.id, reward)

    position_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    pos_emoji = position_emojis[new_count - 1] if new_count <= len(position_emojis) else "✅"

    await update.message.reply_text(
        f"{pos_emoji} *{user.first_name} has entered!*\n\n"
        f"🪙 Claimed: `{reward}` coins\n"
        f"📊 Spot: {new_count}/{slots}\n"
        f"{'⏳ ' + str(remaining) + ' spots remaining...' if remaining > 0 else '🔒 Event Full!'}",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Event close callback ──────────────────────────────────────────────────
async def close_event(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    event_name = job.data["event_name"]

    # Clear event
    await redis_client.delete(f"event_active:{chat_id}")
    await redis_client.delete(f"event:{chat_id}")
    await redis_client.delete(f"event_entrants:{chat_id}")

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🌑 *{event_name}* has ended.\n\n"
             f"_The rift closes. The Oracle returns to silence._\n"
             f"_Watch for the next sign..._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /eventcheck ──────────────────────────────────────────────────────────
async def eventcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    active = await redis_client.get(f"event_active:{chat.id}")

    if not active:
        await update.message.reply_text(
            "🌑 No event active right now.\n_The Oracle rests between hours._"
        )
        return

    event_data = await redis_client.get(f"event:{chat.id}")
    if not event_data:
        return

    parts = event_data.split("|")
    event_name = parts[0]
    slots = int(parts[1])

    entrants_key = f"event_entrants:{chat.id}"
    existing = await redis_client.lrange(entrants_key, 0, -1)
    count = len(existing) if existing else 0

    await update.message.reply_text(
        f"⚡ *EVENT ACTIVE*\n\n"
        f"📌 {event_name}\n"
        f"👥 Entrants: `{count}/{slots}`\n\n"
        f"_Type `/enter` to claim your spot!_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Weekly summary (scheduled job) ───────────────────────────────────────
async def weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    """Auto-posts weekly group summary every Sunday night."""
    chat_id = context.job.data.get("chat_id")
    if not chat_id:
        return

    # Get top 3 coin holders
    try:
        keys = await redis_client.keys("coins:*")
    except Exception:
        return

    leaderboard = []
    for key in (keys or []):
        uid = int(key.split(":")[1])
        val = await redis_client.get(key)
        coins = int(val) if val else 0
        if coins > 0:
            leaderboard.append((uid, coins))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top3 = leaderboard[:3]

    medals = ["🥇", "🥈", "🥉"]
    top_lines = []
    for i, (uid, coins) in enumerate(top3):
        try:
            member = await context.bot.get_chat(uid)
            name = member.first_name or "???"
        except Exception:
            name = "Shadow"
        top_lines.append(f"{medals[i]} {name} — `{coins}` 🪙")

    top_text = "\n".join(top_lines) if top_lines else "_No data_"

    weekly_moods = [
        "Chaotic Neutral", "Eerily Calm", "Collectively Unhinged",
        "Surprisingly Wholesome", "Chaotic Good", "Suspiciously Quiet"
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📊 *MIDNIGHT ORACLE — WEEKLY REPORT*\n"
             f"_{datetime.now().strftime('%d %B %Y')}_\n\n"
             f"🏆 *Top Coin Holders:*\n{top_text}\n\n"
             f"🌙 *Group Mood this Week:* _{random.choice(weekly_moods)}_\n\n"
             f"_Use /checkin daily · /leaderboard to see full rankings_\n"
             f"_The Oracle watches. Always._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Register scheduled jobs ───────────────────────────────────────────────
def register_event_jobs(app: Application, group_chat_id: int):
    """
    Call this in your main.py after building the app.
    
    Example:
        from oracle_events import register_event_jobs
        GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
        register_event_jobs(app, GROUP_CHAT_ID)
    
    Add GROUP_CHAT_ID to your .env / Render env vars.
    """
    jq = app.job_queue

    # Weekly summary — every Sunday at 9 PM
    jq.run_daily(
        weekly_summary,
        time=datetime.strptime("21:00", "%H:%M").time(),
        days=(6,),  # Sunday
        data={"chat_id": group_chat_id},
        name="weekly_summary"
    )
