"""Baithak / Arden — premium Telegram entry surface."""
from __future__ import annotations

import hashlib
import random
from datetime import date

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

SEP = "┄" * 18

# Public help intentionally excludes autonomous/hidden features and owner-only tools.
# Only commands currently exposed by the canonical command menu are listed here.
HELP_TEXT = f"""🖤 *ARDEN*
{SEP}
*she doesn't announce herself. you notice.*

A quiet presence for your group — conversations, games, bonds, little rituals,
and the occasional surprise.

━━━━ *💬 TALK* ━━━━
`/chat` — toggle chat mode
`/persona` — set the chat style
`/vent` — say something anonymously

━━━━ *🎮 PLAY* ━━━━
`/quiz` — quick quiz
`/truth` — truth
`/dare` — dare
`/wyr` — would you rather
`/rps` — rock, paper, scissors
`/riddle` — solve a riddle
`/scramble` — unscramble a word
`/guess` — guess the number
`/leaderboard` — see the rankings
`/dice` — roll the dice
`/darts` — play darts
`/basketball` — shoot
`/bowling` — bowl
`/football` — take a shot
`/slot` — spin

━━━━ *👥 PEOPLE* ━━━━
`/bestie` — find your bestie
`/duo` — pair up
`/friendship` — check a friendship
`/ship` — ship two people
`/matchmaker` — let fate choose
`/friendshiptest` — test the bond
`/hug` `/pat` `/highfive` `/slap` `/kiss` `/poke` `/cuddle` `/wave` `/bite` `/tickle` — send a reaction

━━━━ *✨ EXPLORE* ━━━━
`/oracle` — a reading
`/aura` — scan your aura
`/vibecheck` — check your vibe
`/identity` — your archetype
`/shadow` — meet your shadow
`/element` — your element
`/corecode` — your core words
`/universe` — a message
`/ritual` — today's ritual
`/duality` — your two sides
`/nightreport` — tonight's report
`/sigil` — your sigil
`/glitch` — a system reading

━━━━ *💰 ECONOMY* ━━━━
`/balance` — check your coins
`/daily` — claim your daily reward
`/work` — earn coins
`/richest` — richest members
`/gamble` — gamble coins
`/cgift @user amount` — gift coins
`/rob @user` — attempt a heist
`/shop` — browse the shop
`/buy` — buy an item
`/inventory` — see your inventory
`/chests` — open your daily reward

━━━━ *🛠 UTILITY* ━━━━
`/id` — show an ID
`/info` — inspect a member
`/remind` — set a reminder
`/afk` — mark yourself away
`/groupinfo` — group information
`/stats` — group activity
`/topactive` — most active members
`/msgcount` — message count
`/rank` — activity rank

{SEP}
*Some things here have no command.*

*You'll notice them when they happen.*

✦ *— Arden*"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "there")
    seed = int(hashlib.md5(f"{user.id if user else 0}{date.today()}".encode()).hexdigest(), 16)
    openers = [
        f"_{name}. you found the door._\n\n",
        f"_hey {name}. here's your way around._\n\n",
        f"_{name}. welcome in._\n\n",
        f"_you made it, {name}._\n\n",
    ]
    opener = random.Random(seed).choice(openers)
    try:
        await update.message.reply_text(
            opener + HELP_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception:
        clean = HELP_TEXT.replace("*", "").replace("_", "").replace("`", "")
        await update.message.reply_text(opener.replace("_", "") + clean)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "there")
    chat = update.effective_chat

    if chat.type == "private":
        text = (
            f"🖤 *Arden*\n{SEP}\n\n"
            f"_{name}._\n\n"
            f"_she doesn't announce herself. you notice._\n\n"
            f"_come in. talk. play. connect._\n"
            f"_some things don't need a command._\n\n"
            f"_type /help when you want to look around._\n\n"
            f"✦ *— Arden*"
        )
    else:
        text = (
            f"🖤 *Arden is here.*\n{SEP}\n\n"
            f"_no ceremony needed._\n\n"
            f"_talk. play. carry on._\n"
            f"_you'll notice the rest._\n\n"
            f"✦ *— Arden*"
        )

    try:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception:
        await update.message.reply_text(text.replace("*", "").replace("_", "").replace("`", ""))


def register(app):
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
