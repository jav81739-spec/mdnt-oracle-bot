"""
Death Life Games — a bundle of three death-themed mini-games:

  1. SURVIVAL   /survive /revive /deathstatus (also shows survival streak)
     Daily risk roll. Survive and your streak (and coin reward) grows.
     Die and you're "dead" for a few hours unless you pay to /revive.

  2. ROULETTE   /roulette
     Instant one-shot gamble. ~1 in 6 chance you "die" and lose coins /
     get temporarily locked out of games; otherwise you win coins.

  3. MAFIA      /deathgame /joingame /startround /kill /vote /endgame
     Group elimination game. A host starts a lobby, players join, roles
     (Killer vs Civilian) are DMed privately, then the group alternates
     Night (killer picks a target via DM) and Day (group votes to
     eliminate a suspect) until one side wins.

All persisted via handlers/storage.py, same pattern as economy.py and
marriage.py. Coins are shared with the existing economy system.
"""
import random
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden
from handlers.mentions import mention
from handlers import storage
from handlers import economy

STORAGE_KEY = "deathgames"

# {
#   "<chat_id>": {
#     "survival": {"<uid>": {"name": str, "streak": int, "dead_until": iso-str|None}},
#     "mafia": {
#        "status": "lobby" | "night" | "day" | "none",
#        "host": "<uid>" | None,
#        "players": {"<uid>": {"name": str, "role": "killer"/"civilian", "alive": bool}},
#        "order": ["<uid>", ...],          # stable numbering for /kill and /vote
#        "night_target": "<uid>" | None,
#        "votes": {"<voter_uid>": "<target_uid>"},
#     }
#   }
# }
data = {}

SURVIVE_DIE_CHANCE = 0.3
SURVIVE_BASE_REWARD = 40
SURVIVE_STREAK_BONUS = 10
SURVIVE_DEATH_HOURS = 6
REVIVE_COST = 75

ROULETTE_DIE_CHANCE = 1 / 6
ROULETTE_WIN_LOW, ROULETTE_WIN_HIGH = 60, 150
ROULETTE_LOSE_PENALTY = 80

SURVIVAL_EVENTS_DEATH = [
    "You wandered into a haunted alley and never came back 👻",
    "A piano fell on you. Classic. 🎹",
    "You lost a staring contest with a bear 🐻",
    "You tried to pet a stray cat that was actually a small demon 😾",
    "Gravity remembered you exist 🍂",
]
SURVIVAL_EVENTS_LIFE = [
    "You dodged a falling piano and felt alive ✨",
    "You outran a suspicious goose 🦢",
    "You found a lucky coin and pocketed it 🪙",
    "You made it home before the storm hit ⛈️",
    "A black cat crossed your path and somehow it was fine 🐈‍⬛",
]

MIN_MAFIA_PLAYERS = 4


async def load_from_storage():
    """Call once at bot startup to restore game state from Redis."""
    global data
    data = await storage.load(STORAGE_KEY, {})


async def _persist():
    await storage.save(STORAGE_KEY, data)


def _get_chat(chat_id: int):
    cid = str(chat_id)
    data.setdefault(cid, {"survival": {}, "mafia": _fresh_mafia()})
    chat = data[cid]
    chat.setdefault("survival", {})
    chat.setdefault("mafia", _fresh_mafia())
    return chat


def _fresh_mafia():
    return {
        "status": "none",
        "host": None,
        "players": {},
        "order": [],
        "night_target": None,
        "votes": {},
    }


# ---------------------------------------------------------------------
# 1. SURVIVAL
# ---------------------------------------------------------------------

async def survive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)
    now = datetime.datetime.utcnow()

    record = chat["survival"].setdefault(uid, {"name": user.first_name, "streak": 0, "dead_until": None})
    record["name"] = user.first_name

    if record["dead_until"]:
        dead_until = datetime.datetime.fromisoformat(record["dead_until"])
        if now < dead_until:
            remaining = dead_until - now
            mins = int(remaining.total_seconds() // 60)
            await update.message.reply_text(f"💀 You're still dead. Try again in ~{mins} min, or /revive for {REVIVE_COST} coins.")
            return
        record["dead_until"] = None

    if random.random() < SURVIVE_DIE_CHANCE:
        record["streak"] = 0
        record["dead_until"] = (now + datetime.timedelta(hours=SURVIVE_DEATH_HOURS)).isoformat()
        await _persist()
        await update.message.reply_text(
            f"☠️ {random.choice(SURVIVAL_EVENTS_DEATH)}\n\nYou died. Streak reset. "
            f"Locked out for {SURVIVE_DEATH_HOURS}h, or /revive for {REVIVE_COST} coins."
        )
        return

    record["streak"] += 1
    reward = SURVIVE_BASE_REWARD + (record["streak"] * SURVIVE_STREAK_BONUS)
    account = economy._get_account(chat_id, user.id, user.first_name)
    account["coins"] += reward
    await economy._persist()
    await _persist()
    await update.message.reply_text(
        f"❤️ {random.choice(SURVIVAL_EVENTS_LIFE)}\n\n"
        f"You survived! Streak: {record['streak']} 🔥 — +{reward} coins. Balance: {account['coins']}"
    )


async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    uid = str(user.id)
    record = chat["survival"].get(uid)

    if not record or not record["dead_until"]:
        await update.message.reply_text("You're not dead right now.")
        return

    account = economy._get_account(chat_id, user.id, user.first_name)
    if account["coins"] < REVIVE_COST:
        await update.message.reply_text(f"Reviving costs {REVIVE_COST} coins — you have {account['coins']}.")
        return

    account["coins"] -= REVIVE_COST
    record["dead_until"] = None
    await economy._persist()
    await _persist()
    await update.message.reply_text(f"✨ You paid {REVIVE_COST} coins and came back to life. Balance: {account['coins']}")


async def deathstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat_id = update.effective_chat.id
    chat = _get_chat(chat_id)
    record = chat["survival"].get(str(target.id), {"streak": 0, "dead_until": None})

    status = "Alive ❤️"
    if record["dead_until"]:
        dead_until = datetime.datetime.fromisoformat(record["dead_until"])
        if datetime.datetime.utcnow() < dead_until:
            status = "Dead 💀"

    await update.message.reply_text(
        f"🩺 *{target.first_name}'s Survival Status*\n\nStatus: {status}\nStreak: {record['streak']} 🔥",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------
# 2. ROULETTE
# ---------------------------------------------------------------------

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    account = economy._get_account(chat_id, user.id, user.first_name)

    if random.random() < ROULETTE_DIE_CHANCE:
        penalty = min(ROULETTE_LOSE_PENALTY, account["coins"])
        account["coins"] -= penalty
        await economy._persist()
        await update.message.reply_text(f"🔫 *BANG.* You lost {penalty} coins. Balance: {account['coins']}", parse_mode="Markdown")
    else:
        winnings = random.randint(ROULETTE_WIN_LOW, ROULETTE_WIN_HIGH)
        account["coins"] += winnings
        await economy._persist()
        await update.message.reply_text(f"🔫 *click.* Empty chamber — you won {winnings} coins! Balance: {account['coins']}", parse_mode="Markdown")


# ---------------------------------------------------------------------
# 3. MAFIA / ELIMINATION GAME
# ---------------------------------------------------------------------

def _alive_players(mafia: dict):
    return [uid for uid in mafia["order"] if mafia["players"][uid]["alive"]]


def _numbered_list(mafia: dict, uids: list):
    lines = []
    for i, uid in enumerate(uids, start=1):
        lines.append(f"{i}. {mafia['players'][uid]['name']}")
    return "\n".join(lines)


async def deathgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    mafia = chat["mafia"]

    if mafia["status"] != "none":
        await update.message.reply_text("A game is already running or open here. /endgame first if you want to restart.")
        return

    mafia["status"] = "lobby"
    mafia["host"] = str(user.id)
    mafia["players"] = {str(user.id): {"name": user.first_name, "role": None, "alive": True}}
    mafia["order"] = [str(user.id)]
    mafia["night_target"] = None
    mafia["votes"] = {}
    await _persist()
    await update.message.reply_text(
        f"🔪 *Death Life Games: Mafia* lobby opened by {mention(user.id, user.first_name)}!\n\n"
        f"Type /joingame to join. Host runs /startround once at least {MIN_MAFIA_PLAYERS} players have joined.",
        parse_mode="Markdown",
    )


async def joingame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    mafia = chat["mafia"]
    uid = str(user.id)

    if mafia["status"] != "lobby":
        await update.message.reply_text("There's no open lobby right now. Someone can start one with /deathgame.")
        return
    if uid in mafia["players"]:
        await update.message.reply_text("You're already in!")
        return

    mafia["players"][uid] = {"name": user.first_name, "role": None, "alive": True}
    mafia["order"].append(uid)
    await _persist()
    await update.message.reply_text(f"✅ {mention(user.id, user.first_name)} joined! ({len(mafia['order'])} players)", parse_mode="Markdown")


async def startround(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    mafia = chat["mafia"]

    if mafia["status"] != "lobby":
        await update.message.reply_text("No lobby to start. Use /deathgame to open one.")
        return
    if str(user.id) != mafia["host"]:
        await update.message.reply_text("Only the host who opened the lobby can start it.")
        return
    if len(mafia["order"]) < MIN_MAFIA_PLAYERS:
        await update.message.reply_text(f"Need at least {MIN_MAFIA_PLAYERS} players — currently {len(mafia['order'])}.")
        return

    killer_id = random.choice(mafia["order"])
    for uid in mafia["order"]:
        mafia["players"][uid]["role"] = "killer" if uid == killer_id else "civilian"

    failed_dm = []
    for uid in mafia["order"]:
        role = mafia["players"][uid]["role"]
        text = "🔪 You are the *Killer*. DM me /kill <player number> each night." if role == "killer" \
            else "🧑 You are a *Civilian*. Survive and vote out the killer during the day with /vote <player number>."
        try:
            await context.bot.send_message(int(uid), text, parse_mode="Markdown")
        except Forbidden:
            failed_dm.append(mafia["players"][uid]["name"])

    mafia["status"] = "night"
    mafia["night_target"] = None
    await _persist()

    warning = ""
    if failed_dm:
        warning = f"\n\n⚠️ Couldn't DM: {', '.join(failed_dm)} — they need to start a private chat with me first."

    await update.message.reply_text(
        "🌙 *Night falls.* Roles have been sent by DM.\n\n"
        "The Killer is choosing a target...\n"
        "(Waiting for the night action. Civilians, sit tight.)" + warning,
        parse_mode="Markdown",
    )


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Send /kill to me in a private DM, not in the group.")
        return

    user = update.effective_user
    uid = str(user.id)

    # find a chat where this user is the alive killer mid-night
    target_chat_id, mafia = None, None
    for cid, chat in data.items():
        m = chat.get("mafia", {})
        if m.get("status") == "night" and m["players"].get(uid, {}).get("role") == "killer" and m["players"][uid]["alive"]:
            target_chat_id, mafia = cid, m
            break

    if not mafia:
        await update.message.reply_text("You don't have an active night action right now.")
        return
    if not context.args:
        alive = _alive_players(mafia)
        await update.message.reply_text("Usage: /kill <player number>\n\n" + _numbered_list(mafia, alive))
        return

    try:
        idx = int(context.args[0]) - 1
        alive = _alive_players(mafia)
        target_uid = alive[idx]
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid player number.")
        return
    if target_uid == uid:
        await update.message.reply_text("You can't target yourself.")
        return

    mafia["night_target"] = target_uid
    await _persist()

    target_name = mafia["players"][target_uid]["name"]
    await update.message.reply_text(f"🔪 Target locked: {target_name}. Resolving night...")

    # resolve night immediately since it's the only night action in this simplified game
    mafia["players"][target_uid]["alive"] = False
    mafia["status"] = "day"
    mafia["votes"] = {}
    await _persist()

    alive_now = _alive_players(mafia)
    killers_alive = any(mafia["players"][u]["role"] == "killer" for u in alive_now)
    civilians_alive = any(mafia["players"][u]["role"] == "civilian" for u in alive_now)

    try:
        if not civilians_alive:
            mafia["status"] = "none"
            await _persist()
            await context.bot.send_message(int(target_chat_id), f"☠️ {target_name} was killed in the night.\n\n🔪 The Killer wins! Game over.")
        else:
            await context.bot.send_message(
                int(target_chat_id),
                f"☀️ *Day breaks.* {target_name} was found dead 💀\n\n"
                f"Discuss and vote with /vote <player number>.\n\n" + _numbered_list(mafia, alive_now),
                parse_mode="Markdown",
            )
    except Exception:
        pass


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    mafia = chat["mafia"]
    uid = str(user.id)

    if mafia["status"] != "day":
        await update.message.reply_text("It's not voting time right now.")
        return
    if uid not in mafia["players"] or not mafia["players"][uid]["alive"]:
        await update.message.reply_text("You're not an alive player in this game.")
        return
    if not context.args:
        alive = _alive_players(mafia)
        await update.message.reply_text("Usage: /vote <player number>\n\n" + _numbered_list(mafia, alive))
        return

    try:
        idx = int(context.args[0]) - 1
        alive = _alive_players(mafia)
        target_uid = alive[idx]
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid player number.")
        return

    mafia["votes"][uid] = target_uid
    await _persist()

    alive = _alive_players(mafia)
    if len(mafia["votes"]) < len(alive):
        await update.message.reply_text(f"🗳️ Vote counted. ({len(mafia['votes'])}/{len(alive)} votes in)")
        return

    # tally
    tally = {}
    for v in mafia["votes"].values():
        tally[v] = tally.get(v, 0) + 1
    eliminated_uid = max(tally, key=tally.get)
    mafia["players"][eliminated_uid]["alive"] = False
    eliminated_name = mafia["players"][eliminated_uid]["name"]
    eliminated_role = mafia["players"][eliminated_uid]["role"]

    alive_now = _alive_players(mafia)
    killers_alive = any(mafia["players"][u]["role"] == "killer" for u in alive_now)
    civilians_alive = any(mafia["players"][u]["role"] == "civilian" for u in alive_now)

    if not killers_alive:
        mafia["status"] = "none"
        await _persist()
        await update.message.reply_text(
            f"🗳️ The group voted out {eliminated_name} — they were the *{eliminated_role}*!\n\n"
            f"🎉 The Killer is dead. Civilians win!",
            parse_mode="Markdown",
        )
        return
    if not civilians_alive:
        mafia["status"] = "none"
        await _persist()
        await update.message.reply_text(
            f"🗳️ The group voted out {eliminated_name} — they were the *{eliminated_role}*!\n\n"
            f"🔪 No civilians left. The Killer wins!",
            parse_mode="Markdown",
        )
        return

    mafia["status"] = "night"
    mafia["votes"] = {}
    mafia["night_target"] = None
    await _persist()
    await update.message.reply_text(
        f"🗳️ The group voted out {eliminated_name} — they were the *{eliminated_role}*!\n\n"
        f"🌙 Night falls again. The Killer is choosing...",
        parse_mode="Markdown",
    )


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    chat = _get_chat(chat_id)
    mafia = chat["mafia"]

    if mafia["status"] == "none":
        await update.message.reply_text("No game is running right now.")
        return
    if str(user.id) != mafia["host"]:
        await update.message.reply_text("Only the host can end the game.")
        return

    chat["mafia"] = _fresh_mafia()
    await _persist()
    await update.message.reply_text("🛑 Game ended.")
