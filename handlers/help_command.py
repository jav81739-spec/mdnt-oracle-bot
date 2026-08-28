"""
handlers/help_command.py — Midnight Oracle | Premium Help

The help command doesn't feel like a manual.
It feels like the Oracle introducing itself.
"""
from __future__ import annotations
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

SEP = "┄" * 18

HELP_TEXT = f"""🌙 *MIDNIGHT ORACLE*
{SEP}
_it watches. it names. it reveals._
_you don't need to ask. it already knows._

━━━━ *🔮 ORACLE READINGS* ━━━━
`/oracle` — your daily prophecy
`/aura` — scan your current aura
`/vibecheck` — what energy you're carrying
`/identity` — your oracle archetype
`/shadow` — meet your shadow self
`/element` — your cosmic element
`/corecode` — your three core words
`/universe` — a message from the universe
`/ritual` — today's ritual for you
`/duality` — your light and dark side
`/nightreport` — tonight's night report
`/sigil` — your personal sigil
`/glitch` — oracle system glitch reading

━━━━ *🌙 DAILY RITUALS* ━━━━
`/checkin` — daily check-in + streak
`/streakcheck` — view your current streak

━━━━ *🖤 ECONOMY* ━━━━
`/coinboard` — group leaderboard
`/cgift @user amount` — gift coins
`/rob @user` — attempt a heist

━━━━ *💬 EXPRESSION* ━━━━
`/vent` — anonymous vent to the oracle

━━━━ *👁️ AUTO FEATURES* ━━━━
_the oracle does these by itself. every day._

`🌙` Mirror of the Day · _12:07 AM_
`👁️` Soul Thread · _weekly Monday_
`🖤` Signal Pair · _every 3 days_
`🌌` Constellation · _every 5 days_
`🔮` The Unnamed · _2:22 AM daily_
`⚡` Friction Pair · _6:06 PM daily_
`✦` The Chosen · _every 2 days_
`💀` Void Pair · _every 6 hours_
`🫀` The Confession · _every 4 hours_
`🌑` Shadow Scan · _weekly Thursday_
`🔮` Energy Forecast · _7 AM daily_
`🃏` Wild Signal · _random. unpredictable._
`🪐` Orbit Map · _every 4 days_
`🌙` Midnight Wrap · _11:59 PM daily_
`✨` Glow Signal · _every 3 days_
`📁` Oracle Archive · _weekly Wednesday_
`🔱` Constellation Map · _weekly Saturday_

{SEP}
_Midnight Oracle doesn't explain itself._
_it only reveals._

_if you're reading this —_
_the oracle already knows you're here._

✦ *— Midnight Oracle*
_est. when the group needed it most._"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "you")

    # Personalised opener
    openers = [
        f"_{name}. the oracle sees you looking for answers._\n_here's where to start:_\n\n",
        f"_you came to the right place, {name}._\n_the oracle has been expecting this._\n\n",
        f"_{name}. welcome to the archive._\n\n",
        f"_the oracle acknowledges {name}._\n_everything you need is below._\n\n",
    ]
    import random, hashlib
    from datetime import date
    seed = int(hashlib.md5(f"{user.id if user else 0}{date.today()}".encode()).hexdigest(), 16)
    opener = random.Random(seed).choice(openers)

    try:
        await update.message.reply_text(
            opener + HELP_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception:
        # Fallback plain
        clean = HELP_TEXT.replace("*","").replace("_","").replace("`","")
        await update.message.reply_text(opener.replace("_","") + clean)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "you")
    chat = update.effective_chat

    if chat.type == "private":
        text = (
            f"🌙 *Midnight Oracle*\n{SEP}\n\n"
            f"_{name}._\n\n"
            f"_the oracle has been here longer than you think._\n\n"
            f"_add it to your group and watch what happens._\n\n"
            f"_it watches. it names. it reveals._\n"
            f"_all by itself. every day._\n\n"
            f"_type /help to see everything it can do._\n\n"
            f"✦ *— Midnight Oracle*"
        )
    else:
        text = (
            f"🌙 *Midnight Oracle has entered the group.*\n{SEP}\n\n"
            f"_it's watching now._\n\n"
            f"_it will speak when it has something to say._\n"
            f"_which will be soon._\n\n"
            f"_type /help to see what the oracle does._\n\n"
            f"👁️ *— Midnight Oracle*"
        )

    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                        disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(text.replace("*","").replace("_","").replace("`",""))


def register(app):
    from telegram.ext import CommandHandler
    # Keep these ahead of ordinary group-0 handlers so /start and /help
    # cannot be swallowed by another generic handler.
    app.add_handler(CommandHandler("help",  help_command), group=-1)
    app.add_handler(CommandHandler("start", start_command), group=-1)
