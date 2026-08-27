"""Authoritative Midnight V2 help deck.

The legacy entrypoint still installs its historical /help handler before the
V2 layers are installed.  Telegram/PTB allows handlers in different groups to
run for the same update, so both replies were being sent.  V2 now removes any
older /help handlers before installing the authoritative one.
"""
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

HELP = """<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐑𝐀𝐂𝐋𝐄 · 𝐕𝟐</b>
<i>Hinglish mode · social intelligence · games · radio · world events</i>

<b>💞 SOCIAL / BOND</b>
/hug /kiss /pat /kick /slap /punch /highfive /cuddle /poke /bonk /bite
/wave /wink /dance /roast /cheer /comfort /tickle /salute /stare
/handshake /fistbump /shoulderpat /cheers /bond /oraclepair /vow
/bestie /duo /friendship /ship /tagbestie /squad /loyalty
/matchmaker /friendshiptest /randomship /secretadmirer

<b>🏏 MIDNIGHT CRICKET</b>
/cricket — solo skill match
/cricketduel — challenge a member

<b>🎮 GAMES</b>
/quiz /truth /dare /wyr /nhie /rps /riddle /riddleanswer
/scramble /unscramble /guess /leaderboard /dice /darts /basketball
/bowling /football /slot /hangman /hangmanguess /tictactoe /ttt
/wordchain /chainword /trivia /wordle /wordleguess /impostor /revealimpostor

<b>☠️ DEATH GAMES</b>
/deathgame /joingame /startround /survive /revive /deathstatus /roulette
/vote /kill /endgame

<b>🎧 MIDNIGHT RADIO</b>
/midnightplay <i>song</i> /nowplaying /pausemusic /resumemusic /stopmusic

<b>🌙 ORACLE / AESTHETIC</b>
/oracle /tarot /aura /emojiaura /fate /lore /starsign /whisper /confess
/vibe /vibecheck /shadow /element /moodboard /dream /manifest
/settrigger <i>word</i> /triggerinfo /identity /mprofile /achievements
/midnightevent /nightreport /ritual /sigil

<b>💘 CRUSH / RELATIONSHIPS</b>
/crush /clearcrush /marry /accept /divorce /profile /settings

<b>💰 ECONOMY</b>
/daily /balance /wallet /deposit /withdraw /setpass /changepass
/work /chests /shop /buy /inventory /gift /rob /gamble /richest

<b>🎉 FUN</b>
/compliment /8ball /quote /ratethis /roast

<b>🛠️ UTILITY</b>
/chat /persona /id /info /remind /afk /groupinfo /poll /rank /stats
/topactive /msgcount /joined /left /timecapsule /capsules /report

<b>⚙️ GROUP ADMIN</b>
/mute /unmute /ban /kick /warn /warnings /clearwarns /pin /unpin
/purge /rules /setrules /lock /unlock /setwelcome /setgoodbye /invite

<b>🛠️ UPGRADE</b>
/upgradhelp

<i>Midnight watches the room, remembers durable game state, wakes quiet
groups carefully, chooses pairings automatically, and keeps the night alive.</i>
"""


def _remove_existing_help_handlers(application) -> None:
    """Remove legacy /help handlers so only the V2 help deck replies."""
    for group, handlers in list(application.handlers.items()):
        kept = []
        for handler in handlers:
            commands = getattr(handler, "commands", None)
            if commands and "help" in commands:
                continue
            kept.append(handler)
        application.handlers[group] = kept


async def help_v2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        HELP,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def install(application) -> None:
    _remove_existing_help_handlers(application)
    application.add_handler(CommandHandler("help", help_v2), group=-32)
