"""Authoritative Midnight V2 help deck."""
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

HELP = """<b>☾ 𝐌𝐈𝐃𝐍𝐈𝐆𝐇𝐓 𝐎𝐑𝐀𝐂𝐋𝐄 · 𝐕𝟐</b>
<i>Hinglish mode · social intelligence · games · radio · world events</i>

<b>💞 SOCIAL / BOND</b>
/hug /kiss /pat /kick /slap /punch /highfive
/cuddle /poke /bonk /bite /wave /wink /dance
/roast /cheer /comfort /tickle /salute /stare
/handshake /fistbump /shoulderpat /cheers
/bond /oraclepair /vow

<b>🏏 MIDNIGHT CRICKET</b>
/cricket — solo skill match
/cricketduel — challenge a member
<i>No economy farming. Read the risk, pick the shot.</i>

<b>☠️ DEATH GAMES</b>
/deathgame — open Mafia-style lobby
/joingame — enter the lobby
/startround — host starts the night
/survive — personal survival run
/revive — return early
/deathstatus — check a soul
/roulette — high-risk mini game
/vote /kill /endgame — active-game actions

<b>🎧 MIDNIGHT RADIO</b>
/midnightplay <i>song</i>
/nowplaying · /pausemusic · /resumemusic · /stopmusic
<i>Voice chat playback requires the dedicated MTProto assistant session.</i>

<b>🌙 ORACLE / WORLD</b>
/settrigger <i>word</i> · /triggerinfo
/mprofile /identity /achievements
/aura /vibecheck /shadow /element
/midnightevent /nightreport /ritual /sigil

<b>🛠️ UPGRADE</b>
/upgradhelp

<i>Midnight watches the room, wakes quiet groups carefully, chooses pairings automatically, reacts to associated-channel posts contextually, and keeps game state durable.</i>
"""


async def help_v2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def install(application) -> None:
    application.add_handler(CommandHandler("help", help_v2), group=-32)
