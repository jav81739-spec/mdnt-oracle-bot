"""Midnight Oracle premium Telegram entry surface."""
from __future__ import annotations

import hashlib
import random
from datetime import date

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

SEP = "┄" * 18

HELP_TEXT = f"""🌙 *MIDNIGHT ORACLE*
{SEP}
*it watches. it names. it reveals.*

A quiet presence for your group — readings, games, bonds, economy,
conversation, and surprises you won't find listed here.

━━━━ *🔮 ORACLE* ━━━━
`/oracle` — daily prophecy
`/aura` — scan your aura
`/vibecheck` — check your energy
`/identity` — your archetype
`/shadow` — meet your shadow
`/element` — your cosmic element
`/corecode` — your three core words
`/universe` — a message from the universe
`/ritual` — today's ritual
`/duality` — your light and dark side
`/nightreport` — tonight's report
`/sigil` — your personal sigil
`/glitch` — oracle system reading

━━━━ *🌙 DAILY* ━━━━
`/checkin` — daily check-in + streak
`/streakcheck` — view your streak
`/vent` — anonymous vent

━━━━ *🎮 GAMES* ━━━━
`/quiz` `/truth` `/dare` `/wyr` `/nhie` `/rps`
`/riddle` `/riddleanswer` `/scramble` `/unscramble` `/guess`
`/dice` `/darts` `/basketball` `/bowling` `/football` `/slot`
`/leaderboard` — game rankings

━━━━ *👥 BONDS* ━━━━
`/bestie` `/duo` `/friendship` `/ship`
`/matchmaker` `/friendshiptest`
`/hug` `/pat` `/highfive` `/slap` `/kiss` `/poke` `/cuddle` `/wave` `/bite` `/tickle`

━━━━ *💰 ECONOMY* ━━━━
`/balance` `/daily` `/work` `/richest` `/gamble`
`/cgift @user amount` `/rob @user`
`/shop` `/buy` `/inventory` `/chests`

━━━━ *🛠 UTILITY* ━━━━
`/id` `/info` `/remind` `/afk` `/groupinfo`
`/stats` `/topactive` `/msgcount` `/rank`

{SEP}
*The Oracle has a few things it doesn't announce.*

*You'll notice them when they happen.*

✦ *— Midnight Oracle*"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "there")
    seed = int(hashlib.md5(f"{user.id if user else 0}{date.today()}".encode()).hexdigest(), 16)
    opener = random.Random(seed).choice([
        f"_{name}. you found the door._\n\n",
        f"_hey {name}. here's your way around._\n\n",
        f"_{name}. welcome back._\n\n",
        f"_you made it, {name}._\n\n",
    ])
    try:
        await update.message.reply_text(opener + HELP_TEXT, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text((opener + HELP_TEXT).replace("*", "").replace("_", "").replace("`", ""))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "there")
    chat = update.effective_chat
    if chat.type == "private":
        text = (
            f"🌙 *Midnight Oracle*\n{SEP}\n\n"
            f"_{name}._\n\n"
            f"_the oracle has been here longer than you think._\n\n"
            f"_it watches. it names. it reveals._\n"
            f"_type /help to enter the archive._\n\n"
            f"✦ *— Midnight Oracle*"
        )
    else:
        text = (
            f"🌙 *Midnight Oracle is here.*\n{SEP}\n\n"
            f"_no ceremony needed._\n\n"
            f"_talk. play. carry on._\n"
            f"_you'll notice the rest._\n\n"
            f"✦ *— Midnight Oracle*"
        )
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(text.replace("*", "").replace("_", "").replace("`", ""))


def register(app):
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
