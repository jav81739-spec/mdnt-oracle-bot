"""Second-generation death games engine.

This module intentionally keeps the existing command names while replacing
process-local mutable state with a single durable state document protected by
distributed locks. It is activated by the production entrypoint without
removing the old implementation until the replacement has passed CI.
"""
from __future__ import annotations

import datetime
import random
from typing import Any

from telegram import Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes

from core.economy import EconomyError, service as economy
from core.storage import storage
from handlers.mentions import mention

STORAGE_KEY = "deathgames:v2"
LEGACY_KEY = "deathgames"

SURVIVE_DIE_CHANCE = 0.3
SURVIVE_BASE_REWARD = 40
SURVIVE_STREAK_BONUS = 10
SURVIVE_DEATH_HOURS = 6
REVIVE_COST = 75
ROULETTE_DIE_CHANCE = 1 / 6
ROULETTE_WIN_LOW, ROULETTE_WIN_HIGH = 60, 150
ROULETTE_LOSE_PENALTY = 80
MIN_MAFIA_PLAYERS = 4

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


def _fresh_mafia() -> dict[str, Any]:
    return {"status": "none", "host": None, "players": {}, "order": [], "night_target": None, "votes": {}}


def _fresh() -> dict[str, Any]:
    return {"chats": {}}


def _chat(state: dict[str, Any], chat_id: int) -> dict[str, Any]:
    return state.setdefault("chats", {}).setdefault(str(chat_id), {"survival": {}, "mafia": _fresh_mafia()})


async def load_from_storage() -> None:
    if await storage.exists(STORAGE_KEY):
        return
    legacy = await storage.load(LEGACY_KEY, {})
    migrated = {"chats": legacy} if isinstance(legacy, dict) and legacy else _fresh()
    await storage.set(STORAGE_KEY, migrated)


async def _load() -> dict[str, Any]:
    state = await storage.load(STORAGE_KEY, _fresh())
    return state if isinstance(state, dict) else _fresh()


async def _save(state: dict[str, Any]) -> None:
    if not await storage.set(STORAGE_KEY, state):
        raise RuntimeError("death-game state could not be persisted")


def _alive(mafia: dict[str, Any]) -> list[str]:
    return [uid for uid in mafia["order"] if mafia["players"].get(uid, {}).get("alive")]


def _numbered(mafia: dict[str, Any], uids: list[str]) -> str:
    return "\n".join(f"{i}. {mafia['players'][uid]['name']}" for i, uid in enumerate(uids, 1))


async def survive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await _load()
        chat = _chat(state, cid)
        record = chat["survival"].setdefault(uid, {"name": user.first_name, "streak": 0, "dead_until": None})
        record["name"] = user.first_name
        now = datetime.datetime.now(datetime.timezone.utc)
        if record.get("dead_until"):
            dead_until = datetime.datetime.fromisoformat(record["dead_until"])
            if now < dead_until:
                mins = int((dead_until - now).total_seconds() // 60)
                await update.message.reply_text(f"💀 You're still dead. Try again in ~{mins} min, or /revive for {REVIVE_COST} coins.")
                return
            record["dead_until"] = None
        if random.random() < SURVIVE_DIE_CHANCE:
            record["streak"] = 0
            record["dead_until"] = (now + datetime.timedelta(hours=SURVIVE_DEATH_HOURS)).isoformat()
            await _save(state)
            text = f"☠️ {random.choice(SURVIVAL_EVENTS_DEATH)}\n\nYou died. Streak reset. Locked out for {SURVIVE_DEATH_HOURS}h, or /revive for {REVIVE_COST} coins."
        else:
            record["streak"] = int(record.get("streak", 0)) + 1
            reward = SURVIVE_BASE_REWARD + record["streak"] * SURVIVE_STREAK_BONUS
            try:
                tx = await economy.add(user.id, reward, "survival", scope=str(cid))
            except EconomyError as exc:
                await update.message.reply_text(f"⏳ Survival reward failed safely: {exc}")
                return
            await _save(state)
            text = f"❤️ {random.choice(SURVIVAL_EVENTS_LIFE)}\n\nYou survived! Streak: {record['streak']} 🔥 — +{reward} coins. Balance: {tx.balance}"
    await update.message.reply_text(text)


async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await _load()
        record = _chat(state, cid)["survival"].get(uid)
        if not record or not record.get("dead_until"):
            await update.message.reply_text("You're not dead right now.")
            return
        try:
            tx = await economy.remove(user.id, REVIVE_COST, "revive", scope=str(cid))
        except EconomyError:
            await update.message.reply_text(f"Reviving costs {REVIVE_COST} coins — you have {await economy.balance(user.id, str(cid))}.")
            return
        record["dead_until"] = None
        await _save(state)
    await update.message.reply_text(f"✨ You paid {REVIVE_COST} coins and came back to life. Balance: {tx.balance}")


async def deathstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    record = _chat(await _load(), update.effective_chat.id)["survival"].get(str(target.id), {"streak": 0, "dead_until": None})
    dead = bool(record.get("dead_until") and datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(record["dead_until"]))
    await update.message.reply_text(f"🩺 *{target.first_name}'s Survival Status*\n\nStatus: {'Dead 💀' if dead else 'Alive ❤️'}\nStreak: {record.get('streak', 0)} 🔥", parse_mode="Markdown")


async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid = update.effective_user, update.effective_chat.id
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        if random.random() < ROULETTE_DIE_CHANCE:
            balance = await economy.balance(user.id, str(cid))
            penalty = min(ROULETTE_LOSE_PENALTY, balance)
            try:
                tx = await economy.remove(user.id, penalty, "roulette-loss", scope=str(cid)) if penalty else None
            except EconomyError:
                await update.message.reply_text("⏳ Roulette couldn't settle safely — try again.")
                return
            text = f"🔫 *BANG.* You lost {penalty} coins. Balance: {tx.balance if tx else balance}"
        else:
            winnings = random.randint(ROULETTE_WIN_LOW, ROULETTE_WIN_HIGH)
            try:
                tx = await economy.add(user.id, winnings, "roulette-win", scope=str(cid))
            except EconomyError as exc:
                await update.message.reply_text(f"⏳ Roulette couldn't settle safely: {exc}")
                return
            text = f"🔫 *click.* Empty chamber — you won {winnings} coins! Balance: {tx.balance}"
    await update.message.reply_text(text, parse_mode="Markdown")


async def deathgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid = update.effective_user, update.effective_chat.id
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await _load()
        mafia = _chat(state, cid)["mafia"]
        if mafia["status"] != "none":
            await update.message.reply_text("A game is already running or open here. /endgame first.")
            return
        mafia.clear(); mafia.update({"status": "lobby", "host": str(user.id), "players": {str(user.id): {"name": user.first_name, "role": None, "alive": True}}, "order": [str(user.id)], "night_target": None, "votes": {}})
        await _save(state)
    await update.message.reply_text(f"🔪 *Death Life Games: Mafia* lobby opened by {mention(user.id, user.first_name)}!\n\nType /joingame to join. Host runs /startround once at least {MIN_MAFIA_PLAYERS} players have joined.", parse_mode="Markdown")


async def joingame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await _load(); mafia = _chat(state, cid)["mafia"]
        if mafia["status"] != "lobby":
            await update.message.reply_text("There's no open lobby right now. Someone can start one with /deathgame.")
            return
        if uid in mafia["players"]:
            await update.message.reply_text("You're already in!")
            return
        mafia["players"][uid] = {"name": user.first_name, "role": None, "alive": True}; mafia["order"].append(uid)
        await _save(state); count = len(mafia["order"])
    await update.message.reply_text(f"✅ {mention(user.id, user.first_name)} joined! ({count} players)", parse_mode="Markdown")


async def startround(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid = update.effective_user, update.effective_chat.id
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again.")
            return
        state = await _load(); mafia = _chat(state, cid)["mafia"]
        if mafia["status"] != "lobby":
            await update.message.reply_text("No lobby to start. Use /deathgame to open one."); return
        if str(user.id) != mafia["host"]:
            await update.message.reply_text("Only the host can start it."); return
        if len(mafia["order"]) < MIN_MAFIA_PLAYERS:
            await update.message.reply_text(f"Need at least {MIN_MAFIA_PLAYERS} players — currently {len(mafia['order'])}."); return
        killer_id = random.choice(mafia["order"])
        for uid in mafia["order"]: mafia["players"][uid]["role"] = "killer" if uid == killer_id else "civilian"
        mafia["status"] = "night"; mafia["night_target"] = None; mafia["votes"] = {}
        await _save(state)
        players = [(uid, p["role"], p["name"]) for uid, p in mafia["players"].items()]
    failed = []
    for uid, role, name in players:
        try:
            await context.bot.send_message(int(uid), "🔪 You are the *Killer*. DM /kill <player number>." if role == "killer" else "🧑 You are a *Civilian*. Vote with /vote <player number> during the day.", parse_mode="Markdown")
        except Forbidden:
            failed.append(name)
    warning = f"\n\n⚠️ Couldn't DM: {', '.join(failed)} — start a private chat with me first." if failed else ""
    await update.message.reply_text("🌙 *Night falls.* Roles have been sent by DM.\n\nThe Killer is choosing a target..." + warning, parse_mode="Markdown")


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Send /kill to me in a private DM, not in the group."); return
    uid = str(update.effective_user.id)
    async with storage.lock("deathgames-global") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again."); return
        state = await _load(); found = None
        for cid, chat in state.get("chats", {}).items():
            mafia = chat.get("mafia", {}); player = mafia.get("players", {}).get(uid, {})
            if mafia.get("status") == "night" and player.get("role") == "killer" and player.get("alive"):
                found = (cid, mafia); break
        if not found:
            await update.message.reply_text("You don't have an active night action right now."); return
        cid, mafia = found; alive = _alive(mafia)
        if not context.args:
            await update.message.reply_text("Usage: /kill <player number>\n\n" + _numbered(mafia, alive)); return
        try: target_uid = alive[int(context.args[0]) - 1]
        except (ValueError, IndexError):
            await update.message.reply_text("Invalid player number."); return
        if target_uid == uid:
            await update.message.reply_text("You can't target yourself."); return
        mafia["night_target"] = target_uid; mafia["players"][target_uid]["alive"] = False
        target_name = mafia["players"][target_uid]["name"]; alive_now = _alive(mafia)
        civilians_alive = any(mafia["players"][u]["role"] == "civilian" for u in alive_now)
        if civilians_alive:
            mafia["status"] = "day"; mafia["votes"] = {}; result = "day"
        else:
            mafia.clear(); mafia.update(_fresh_mafia()); result = "killer"
        await _save(state)
    if result == "killer":
        await context.bot.send_message(int(cid), f"☠️ {target_name} was killed in the night.\n\n🔪 The Killer wins! Game over.")
    else:
        await context.bot.send_message(int(cid), f"☀️ *Day breaks.* {target_name} was found dead 💀\n\nVote with /vote <player number>.\n\n" + _numbered(mafia, alive_now), parse_mode="Markdown")
    await update.message.reply_text(f"🔪 Target locked: {target_name}. Night resolved.")


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid, uid = update.effective_user, update.effective_chat.id, str(update.effective_user.id)
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired:
            await update.message.reply_text("⏳ The game engine is busy — try again."); return
        state = await _load(); mafia = _chat(state, cid)["mafia"]
        if mafia["status"] != "day": await update.message.reply_text("It's not voting time right now."); return
        if uid not in mafia["players"] or not mafia["players"][uid]["alive"]: await update.message.reply_text("You're not an alive player in this game."); return
        alive = _alive(mafia)
        if not context.args: await update.message.reply_text("Usage: /vote <player number>\n\n" + _numbered(mafia, alive)); return
        try: target_uid = alive[int(context.args[0]) - 1]
        except (ValueError, IndexError): await update.message.reply_text("Invalid player number."); return
        mafia["votes"][uid] = target_uid
        if len(mafia["votes"]) < len(alive):
            await _save(state); await update.message.reply_text(f"🗳️ Vote counted. ({len(mafia['votes'])}/{len(alive)} votes in)"); return
        tally: dict[str, int] = {}
        for target in mafia["votes"].values(): tally[target] = tally.get(target, 0) + 1
        eliminated_uid = max(tally, key=tally.get); eliminated = mafia["players"][eliminated_uid]
        eliminated["alive"] = False; alive_now = _alive(mafia)
        killers_alive = any(mafia["players"][u]["role"] == "killer" for u in alive_now)
        civilians_alive = any(mafia["players"][u]["role"] == "civilian" for u in alive_now)
        if not killers_alive or not civilians_alive:
            winner = "Civilians" if not killers_alive else "Killer"; role = eliminated["role"]; name = eliminated["name"]
            mafia.clear(); mafia.update(_fresh_mafia()); text = f"🗳️ The group voted out {name} — they were the *{role}*!\n\n🎉 {winner} win!"
        else:
            mafia["status"] = "night"; mafia["votes"] = {}; mafia["night_target"] = None
            text = f"🗳️ The group voted out {eliminated['name']} — they were the *{eliminated['role']}*!\n\n🌙 Night falls again. The Killer is choosing..."
        await _save(state)
    await update.message.reply_text(text, parse_mode="Markdown")


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, cid = update.effective_user, update.effective_chat.id
    async with storage.lock(f"deathgames:{cid}") as acquired:
        if not acquired: await update.message.reply_text("⏳ The game engine is busy — try again."); return
        state = await _load(); mafia = _chat(state, cid)["mafia"]
        if mafia["status"] == "none": await update.message.reply_text("No game is running right now."); return
        if str(user.id) != mafia["host"]: await update.message.reply_text("Only the host can end the game."); return
        mafia.clear(); mafia.update(_fresh_mafia()); await _save(state)
    await update.message.reply_text("🛑 Game ended.")
