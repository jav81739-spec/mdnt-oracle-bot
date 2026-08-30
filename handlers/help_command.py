"""Premium member help for Midnight Oracle.

Only executable member commands are shown. Private/admin controls and the
Oracle's autonomous scheduler are intentionally kept out of this map.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

SEP = "┄" * 18
ADMIN_ONLY = {
    "broadcast", "announce", "midnightmap", "ownerstatus", "ownerstats",
    "setcommands", "reload", "shutdown", "restart", "admin", "moderation",
}
SECTIONS = [
    ("🔮 READINGS", ["oracle", "aura", "vibecheck", "identity", "shadow", "element", "corecode", "universe", "ritual", "duality", "nightreport", "sigil", "glitch"]),
    ("🌙 DAILY & MEMORY", ["checkin", "streakcheck", "memory", "mymemory", "forget", "tod", "house", "quiet", "wake"]),
    ("🫂 BONDS & SOCIAL", ["hug", "kiss", "pat", "kick", "slap", "punch", "highfive", "cuddle", "poke", "bonk", "bite", "wave", "wink", "dance", "roast", "cheer", "comfort", "tickle", "salute", "stare", "handshake", "fistbump", "shoulderpat", "cheers"]),
    ("💞 RELATIONSHIPS", ["bond", "oraclepair", "vow", "bestie", "duo", "friendship", "ship", "tagbestie", "squad", "loyalty", "matchmaker", "friendshiptest", "randomship", "secretadmirer"]),
    ("🪞 ORACLE SIGNALS", ["weave", "orbit", "echo", "anchor", "fracture", "ember", "mirror", "crossing", "undertow", "gaze", "release", "veil"]),
    ("🎮 GAMES", ["quiz", "truth", "dare", "wyr", "nhie", "rps", "riddle", "riddleanswer", "scramble", "unscramble", "guess", "dice", "darts", "basketball", "bowling", "football", "leaderboard"]),
    ("🏏 MIDNIGHT CRICKET", ["cricket", "cricketduel"]),
    ("💀 DEATH GAMES", ["deathgame", "joingame", "startround", "survive", "revive", "deathstatus", "roulette", "vote", "kill", "endgame"]),
    ("🪙 ECONOMY", ["coinboard", "cgift", "rob"]),
    ("🫀 EXPRESSION", ["vent"]),
]

def _live_member_commands(application) -> set[str]:
    live = {"start", "help"}
    for handlers in getattr(application, "handlers", {}).values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                for command in getattr(handler, "commands", ()):
                    name = str(command).lower().lstrip("/")
                    if name and name not in ADMIN_ONLY and len(name) <= 32:
                        live.add(name)
    return live

def _box(title: str, commands: list[str], live: set[str]) -> str | None:
    alive = [f"`/{name}`" for name in commands if name in live]
    if not alive:
        return None
    lines = [f"*{title}*", SEP]
    for i in range(0, len(alive), 7):
        lines.append(" · ".join(alive[i:i + 7]))
    return "\n".join(lines)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "you")
    live = _live_member_commands(context.application)
    opener = random.Random(int(hashlib.md5(f"{user.id if user else 0}{date.today()}".encode()).hexdigest(), 16)).choice([
        f"_{name}. the archive is open._",
        f"_you came to the right place, {name}._",
        f"_the oracle acknowledges {name}._",
        "_the map is yours. choose a door._",
    ])
    boxes = [b for title, commands in SECTIONS if (b := _box(title, commands, live))]
    known = {name for _, commands in SECTIONS for name in commands} | ADMIN_ONLY
    extras = sorted(name for name in live - known if name not in {"start", "help"})
    if extras:
        boxes.append(_box("✦ MORE MEMBER COMMANDS", extras, live))
    header = (
        "🌙 *MIDNIGHT ORACLE*\n" + f"{SEP}\n" + f"{opener}\n\n"
        "_Everything below is manually triggered and currently alive._\n"
    )
    footer = (
        f"\n*✦ {len(live)} LIVE MEMBER COMMANDS*\n{SEP}\n"
        "_Admin controls stay private._\n"
        "_The Oracle's autonomous behaviour is deliberately not listed here._\n\n"
        "_If Telegram's native menu cannot fit every command, /help remains the complete archive._\n\n"
        "✦ *— Midnight Oracle*"
    )
    try:
        await update.message.reply_text(header + "\n\n".join(b for b in boxes if b) + footer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        clean = (header + "\n\n".join(b for b in boxes if b) + footer).replace("*", "").replace("_", "").replace("`", "")
        await update.message.reply_text(clean)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "you")
    chat = update.effective_chat
    if chat.type == "private":
        text = f"🌙 *Midnight Oracle*\n{SEP}\n\n_{name}._\n\n_the oracle has been here longer than you think._\n\n_type /help to open the complete member command archive._\n\n✦ *— Midnight Oracle*"
    else:
        text = f"🌙 *Midnight Oracle has entered the group.*\n{SEP}\n\n_it's watching now._\n\n_type /help to open the complete member command archive._\n\n👁️ *— Midnight Oracle*"
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(text.replace("*", "").replace("_", "").replace("`", ""))

def register(app):
    app.add_handler(CommandHandler("help", help_command), group=-1)
    app.add_handler(CommandHandler("start", start_command), group=-1)
