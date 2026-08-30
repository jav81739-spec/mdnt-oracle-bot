"""
handlers/help_command.py — Midnight Oracle | Premium Help

The help command doesn't feel like a manual.
It feels like the Oracle introducing itself.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler

SEP = "┄" * 18

# Telegram's native command menu is capped, so /help is the complete member
# command directory. Keep sections short and readable rather than one wall of text.
HELP_BOXES = [
    f"""🌙 *MIDNIGHT ORACLE*\n{SEP}\n_The command map — without the command dump._\n\n*🔮 READINGS*\n`/oracle` · `/aura` · `/vibecheck` · `/identity`\n`/shadow` · `/element` · `/corecode` · `/universe`\n`/ritual` · `/duality` · `/nightreport` · `/sigil` · `/glitch`""",
    f"""*🌙 DAILY & MEMORY*\n{SEP}\n`/checkin` · `/streakcheck`\n`/memory` · `/mymemory` · `/forget`\n`/tod` · `/house` · `/quiet` · `/wake`\n`/truth` · `/wyr` · `/nhie`""",
    f"""*🫂 BONDS & SOCIAL*\n{SEP}\n`/hug` · `/kiss` · `/pat` · `/kick` · `/slap` · `/punch`\n`/highfive` · `/cuddle` · `/poke` · `/bonk` · `/bite`\n`/wave` · `/wink` · `/dance` · `/roast` · `/cheer`\n`/comfort` · `/tickle` · `/salute` · `/stare` · `/handshake`\n`/fistbump` · `/shoulderpat` · `/cheers`""",
    f"""*💞 RELATIONSHIPS*\n{SEP}\n`/bond` · `/oraclepair` · `/vow` · `/bestie` · `/duo`\n`/friendship` · `/ship` · `/tagbestie` · `/squad`\n`/loyalty` · `/matchmaker` · `/friendshiptest`\n`/randomship` · `/secretadmirer`""",
    f"""*🪞 ORACLE SIGNALS*\n{SEP}\n`/weave` · `/orbit` · `/echo` · `/anchor` · `/fracture`\n`/ember` · `/mirror` · `/crossing` · `/undertow`\n`/gaze` · `/release` · `/veil`""",
    f"""*🎮 GAMES*\n{SEP}\n`/quiz` · `/rps` · `/riddle` · `/riddleanswer`\n`/scramble` · `/unscramble` · `/guess` · `/dice`\n`/darts` · `/basketball` · `/bowling` · `/football`\n`/leaderboard`""",
    f"""*🧠 QUESTIONS & CHAOS*\n{SEP}\n`/truth` · `/dare` · `/wyr` · `/nhie`\n`/predict` · `/predictions` · `/vent`""",
    f"""*🌙 MIDNIGHT CRICKET*\n{SEP}\n`/cricket` — solo skill match\n`/cricketduel` — challenge another member""",
    f"""*💀 DEATH GAMES*\n{SEP}\n`/deathgame` · `/joingame` · `/startround`\n`/survive` · `/revive` · `/deathstatus` · `/roulette`\n`/vote` · `/kill` · `/endgame`""",
    f"""*🪙 ECONOMY*\n{SEP}\n`/coinboard` · `/cgift` · `/rob`""",
    f"""*🫀 EXPRESSION*\n{SEP}\n`/vent` — say it without needing a perfect sentence\n\n*The Oracle's autonomous rituals are not commands.*\nThey appear when their own clock, signal or room conditions call for them.""",
    f"""*👁️ THE AUTONOMOUS ORACLE*\n{SEP}\n🌙 Mirror of the Day · 12:07 AM\n🔮 Energy Forecast · 7:00 AM\n🔮 The Unnamed · 2:22 AM\n⚡ Friction Pair · 6:06 PM\n🌑 Shadow Scan · weekly\n👁️ Soul Thread · weekly\n🖤 Signal Pair · periodic\n🌌 Constellation · periodic\n✦ The Chosen · periodic\n🪐 Orbit Map · periodic\n💀 Void Pair · several times daily\n🫀 The Confession · several times daily\n🃏 Wild Signal · unpredictable\n📁 Oracle Archive · weekly\n🔱 Constellation Map · weekly\n✨ Glow Signal · periodic\n🌙 Midnight Wrap · 11:59 PM""",
    f"""*✦ ONE LAST THING*\n{SEP}\n_Admin / owner controls stay out of the member command map._\n_The commands above are for the people who make the room alive._\n\n_Type a command manually even if Telegram doesn't show it in the native menu._\n_The Oracle's menu is a doorway. `/help` is the whole archive._\n\n✦ *— Midnight Oracle*""",
]


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user and user.username else (user.first_name if user else "you")

    openers = [
        f"_{name}. the oracle sees you looking for answers._\n_here's the map:_\n\n",
        f"_you came to the right place, {name}._\n_the archive is open._\n\n",
        f"_{name}. welcome to the archive._\n\n",
        f"_the oracle acknowledges {name}._\n_everything for members is below._\n\n",
    ]
    seed = int(hashlib.md5(f"{user.id if user else 0}{date.today()}".encode()).hexdigest(), 16)
    opener = random.Random(seed).choice(openers)

    try:
        await update.message.reply_text(
            opener + HELP_BOXES[0],
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        for box in HELP_BOXES[1:]:
            await update.message.reply_text(
                box,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
    except Exception:
        for index, box in enumerate(HELP_BOXES):
            clean = box.replace("*", "").replace("_", "").replace("`", "")
            prefix = opener.replace("_", "") if index == 0 else ""
            try:
                await update.message.reply_text(prefix + clean)
            except Exception:
                break


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
            f"_type /help to open the complete member command archive._\n\n"
            f"✦ *— Midnight Oracle*"
        )
    else:
        text = (
            f"🌙 *Midnight Oracle has entered the group.*\n{SEP}\n\n"
            f"_it's watching now._\n\n"
            f"_it will speak when it has something to say._\n"
            f"_which will be soon._\n\n"
            f"_type /help to open the complete member command archive._\n\n"
            f"👁️ *— Midnight Oracle*"
        )

    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                        disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(text.replace("*", "").replace("_", "").replace("`", ""))


def register(app):
    # Keep these ahead of ordinary group-0 handlers so /start and /help
    # cannot be swallowed by another generic handler.
    app.add_handler(CommandHandler("help", help_command), group=-1)
    app.add_handler(CommandHandler("start", start_command), group=-1)
