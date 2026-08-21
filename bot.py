import http.server
import socketserver
import threading

def run_dummy_server():
    # Render automatically provides a PORT environment variable
    import os
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

# This runs the dummy server in the background so your bot code can still run
threading.Thread(target=run_dummy_server, daemon=True).start()
"""
bot.py — Midnight Oracle Bot | FINAL VERSION
Webhook mode for Render free tier.

NEW ROOT FILES (upload these alongside bot.py):
  oracle_channel.py     — auto-reply to channel posts in group
  oracle_engagement.py  — /checkin /vent /rob /gift /leaderboard /streakcheck
  oracle_aesthetic.py   — 13 new aesthetic commands
  oracle_mines.py       — /mines game
  oracle_solobet.py     — /bet + bbet shorthand
  oracle_wallet.py      — /wallet /deposit /withdraw /setpass /recover
  oracle_events_mod.py  — /oraclehour /enter /eventcheck + weekly summary
  redis_client.py       — Redis adapter (wraps your storage.py)

handlers/ folder is UNTOUCHED.
"""

import sys
import os
import logging

# ── PATH FIX: ensures Python finds all root-level oracle_*.py files ──────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    filters,
)

# ── New oracle_ modules (NO naming conflict with handlers/) ───────────────
from oracle_channel import get_channel_oracle_handler

from oracle_engagement import (
    checkin_command,
    gift_command        as engagement_gift,
    rob_command         as engagement_rob,
    leaderboard_command as coinboard_command,
    vent_command,
    streakcheck_command,
)

from handlers import (
    aura_command,
    identity_command,
    oracle_command,
    vibecheck_command,
    shadow_command,
    element_command,
    corecode_command,
    universe_command,
    ritual_command,
    duality_command,
    glitch_command,
    nightreport_command,
    sigil_command,
)

from oracle_events_mod import (
    oraclehour_command,
    enter_command,
    eventcheck_command,
    register_event_jobs,
)

from oracle_mines import mines_command, get_mines_handlers

from oracle_solobet import (
    bet_command,
    betstats_command,
    topbet_command,
    get_bbet_handler,
)

from oracle_wallet import (
    wallet_command,
    deposit_command,
    withdraw_command,
    setpass_command,
    changepass_command,
    recover_command,
)

# ── Original handlers/ modules (completely untouched) ────────────────────
from handlers import (
    chat,
    games,
    moderation,
    utility,
    aesthetic,          # handlers/aesthetic.py — tarot, fate, whisper etc.
    friendship,
    fun,
    matchmaking,
    stats,
    events,
    economy,
    timecapsule,
    marriage,
    deathgames,
)

load_dotenv()
TOKEN              = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT               = int(os.getenv("PORT", 10000))
GROUP_CHAT_ID      = int(os.getenv("GROUP_CHAT_ID", "0"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Command menu (99 max) ─────────────────────────────────────────────────
BOT_COMMANDS = [
    # General
    BotCommand("start",          "Welcome message"),
    BotCommand("help",           "List all commands"),

    # Daily engagement
    BotCommand("checkin",        "Daily check-in — earn coins + build streak"),
    BotCommand("streakcheck",    "View your check-in streak"),
    BotCommand("vent",           "Post anonymously to the group"),
    BotCommand("coinboard",      "Coin richlist leaderboard"),

    # Economy
    BotCommand("daily",          "Claim daily coins"),
    BotCommand("balance",        "Check coin balance"),
    BotCommand("rob",            "Try robbing someone (reply)"),
    BotCommand("gamble",         "Gamble your coins"),
    BotCommand("richest",        "Top coin holders"),
    BotCommand("leaderboard",    "Game win rankings"),

    # Wallet / vault
    BotCommand("wallet",         "View your protected coin vault"),
    BotCommand("deposit",        "Lock coins in vault (safe from rob)"),
    BotCommand("withdraw",       "Take coins out of vault"),
    BotCommand("cgift",          "Gift coins to someone (reply to msg)"),
    BotCommand("setpass",        "Set account backup password (DM only)"),
    BotCommand("recover",        "Recover deleted account (DM only)"),

    # Gambling
    BotCommand("bet",            "50/50 solo bet — /bet <amount>"),
    BotCommand("betstats",       "Your betting win/loss stats"),
    BotCommand("topbet",         "Top bettors leaderboard"),
    BotCommand("mines",          "Mines — pick tiles, dodge bombs"),

    # Oracle events
    BotCommand("oraclehour",     "Admin: trigger a group coin event"),
    BotCommand("enter",          "Join an active Oracle event"),
    BotCommand("eventcheck",     "Check if an event is running"),

    # Aesthetic / Mystery — NEW
    BotCommand("oracle",         "Today's personal prophecy"),
    BotCommand("aura",           "Scan your aura color + meaning"),
    BotCommand("identity",       "Your Oracle identity card"),
    BotCommand("vibecheck",      "Full vibe check with stats"),
    BotCommand("shadow",         "Your shadow self revealed"),
    BotCommand("element",        "Your cosmic element"),
    BotCommand("corecode",       "Your 3 core personality words"),
    BotCommand("universe",       "What the universe wants you to know"),
    BotCommand("ritual",         "Today's ritual from the Oracle"),
    BotCommand("duality",        "Your light and dark side"),
    BotCommand("glitch",         "Oracle glitches out"),
    BotCommand("nightreport",    "Tonight's personal energy reading"),
    BotCommand("sigil",          "Your personal text-art sigil"),

    # Aesthetic / Mystery — original
    BotCommand("tarot",          "Draw a tarot card"),
    BotCommand("fate",           "Today's cryptic fate"),
    BotCommand("starsign",       "Zodiac reading"),
    BotCommand("dream",          "AI dream interpretation"),
    BotCommand("manifest",       "Stylized affirmation card"),
    BotCommand("emojiaura",      "Emoji-only energy reading"),
    BotCommand("lore",           "Random group lore drop"),
    BotCommand("moodboard",      "Today's aesthetic mood"),
    BotCommand("confess",        "Anonymous confession"),

    # Games
    BotCommand("quiz",           "Trivia round"),
    BotCommand("truth",          "Truth question"),
    BotCommand("dare",           "Dare challenge"),
    BotCommand("wyr",            "Would you rather"),
    BotCommand("nhie",           "Never have I ever"),
    BotCommand("rps",            "Rock paper scissors vs bot"),
    BotCommand("riddle",         "Get a riddle"),
    BotCommand("scramble",       "Unscramble a word"),
    BotCommand("guess",          "Guess a number 1-20"),
    BotCommand("dice",           "Roll a dice"),
    BotCommand("slot",           "Spin the slot machine"),
    BotCommand("hangman",        "Start hangman"),
    BotCommand("tictactoe",      "Challenge someone to tic-tac-toe"),
    BotCommand("wordchain",      "Start a word chain"),
    BotCommand("trivia",         "Trivia by category"),
    BotCommand("wordle",         "Get today's wordle"),
    BotCommand("impostor",       "Start an impostor round"),

    # Social / Actions
    BotCommand("hug",            "Hug someone (reply)"),
    BotCommand("pat",            "Pat someone (reply)"),
    BotCommand("slap",           "Slap someone (reply)"),
    BotCommand("kiss",           "Kiss someone (reply)"),
    BotCommand("ship",           "Ship two people together"),
    BotCommand("roast",          "Playful roast"),
    BotCommand("compliment",     "Give a compliment"),
    BotCommand("8ball",          "Magic 8-ball answer"),
    BotCommand("quote",          "Random quote"),

    # Friendship
    BotCommand("bestie",         "Declare a bestie"),
    BotCommand("duo",            "Generate a duo name"),
    BotCommand("friendship",     "Compatibility score"),
    BotCommand("loyalty",        "Loyalty score reading"),
    BotCommand("crush",          "Privately pick a crush (reply)"),
    BotCommand("secretadmirer",  "Send someone an anonymous DM"),
    BotCommand("randomship",     "Bot randomly ships two members"),

    # Moderation
    BotCommand("mute",           "Mute a user (admin)"),
    BotCommand("ban",            "Ban a user (admin)"),
    BotCommand("kick",           "Kick a user (admin)"),
    BotCommand("warn",           "Warn a user (admin)"),
    BotCommand("warnings",       "Check warning count"),
    BotCommand("purge",          "Delete N messages (admin)"),
    BotCommand("rules",          "Show group rules"),
    BotCommand("setrules",       "Set group rules (admin)"),

    # Utility
    BotCommand("id",             "Get user/chat ID"),
    BotCommand("info",           "User info card"),
    BotCommand("stats",          "Group activity stats"),
    BotCommand("topactive",      "Most active members"),
    BotCommand("afk",            "Mark yourself away"),
    BotCommand("report",         "Report a message to admins"),
    BotCommand("poll",           "Create a poll: /poll Q | A | B"),
    BotCommand("timecapsule",    "Lock a message for later"),
    BotCommand("capsules",       "List pending time capsules"),

    # Marriage / Shop
    BotCommand("marry",          "Propose to someone (reply)"),
    BotCommand("divorce",        "End a marriage"),
    BotCommand("profile",        "View your Oracle profile"),
    BotCommand("work",           "Earn coins by working"),
    BotCommand("shop",           "Browse the item shop"),
    BotCommand("buy",            "Buy an item from shop"),
    BotCommand("inventory",      "View your inventory"),
    BotCommand("gift",           "Gift a shop item (reply)"),

    # Death Games
    BotCommand("survive",        "Survive the death game"),
    BotCommand("deathgame",      "Start a death game"),
    BotCommand("joingame",       "Join an active death game"),
    BotCommand("roulette",       "Play Russian roulette"),
]


# ── Startup ───────────────────────────────────────────────────────────────
async def _post_init(app: Application):
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("✅ Command menu registered (%d commands).", len(BOT_COMMANDS))

    await economy.load_from_storage()
    logger.info("✅ Economy loaded.")

    await timecapsule.load_and_reschedule(app)
    logger.info("✅ Time capsules rescheduled.")

    await chat.load_from_storage()
    logger.info("✅ Chat mode settings loaded.")

    await marriage.load_from_storage()
    logger.info("✅ Marriage/shop data loaded.")

    await deathgames.load_from_storage()
    logger.info("✅ Death Games data loaded.")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not found. Add it in Render Environment tab.")
    if not RENDER_EXTERNAL_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL not set — auto-set by Render on web services.")

    app = Application.builder().token(TOKEN).post_init(_post_init).build()

    # ── PRIORITY 0: Channel oracle + bbet text trigger ────────────────────
    app.add_handler(get_channel_oracle_handler(),   group=0)
    app.add_handler(get_bbet_handler(),             group=0)

    # ── PRIORITY 1-6: Message tracking (text, AFK, friendship) ───────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat.auto_reply),          group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, friendship.track_message), group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, utility.check_afk_mentions), group=3)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,  chat.maybe_react_to_message), group=4)
    app.add_handler(MessageHandler(filters.Sticker.ALL,             chat.sticker_reply),       group=5)
    app.add_handler(MessageHandler(filters.ANIMATION,               chat.gif_reply),           group=6)

    # ── General ───────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",          utility.start_welcome))
    app.add_handler(CommandHandler("help",           utility.help_command))
    app.add_handler(CommandHandler("chat",           chat.toggle_chat))
    app.add_handler(CommandHandler("persona",        chat.set_persona))
    app.add_handler(CommandHandler("sticker",        chat.send_random_sticker))
    app.add_handler(CommandHandler("getstickerid",   chat.get_sticker_id))
    app.add_handler(CommandHandler("gif",            chat.send_random_gif))

    # ── Engagement (oracle_engagement.py) ─────────────────────────────────
    app.add_handler(CommandHandler("checkin",        checkin_command))
    app.add_handler(CommandHandler("streakcheck",    streakcheck_command))
    app.add_handler(CommandHandler("vent",           vent_command))
    app.add_handler(CommandHandler("cgift",          engagement_gift))
    app.add_handler(CommandHandler("coinboard",      coinboard_command))
    # rob: engagement version (vault-aware) overrides economy.rob
    app.add_handler(CommandHandler("rob",            engagement_rob))

    # ── Oracle Events (oracle_events_mod.py) ──────────────────────────────
    app.add_handler(CommandHandler("oraclehour",     oraclehour_command))
    app.add_handler(CommandHandler("enter",          enter_command))
    app.add_handler(CommandHandler("eventcheck",     eventcheck_command))

    # ── Aesthetic NEW (oracle_aesthetic.py) ───────────────────────────────
    app.add_handler(CommandHandler("oracle",         oracle_command))
    app.add_handler(CommandHandler("aura",           aura_command))
    app.add_handler(CommandHandler("identity",       identity_command))
    app.add_handler(CommandHandler("vibecheck",      vibecheck_command))
    app.add_handler(CommandHandler("shadow",         shadow_command))
    app.add_handler(CommandHandler("element",        element_command))
    app.add_handler(CommandHandler("corecode",       corecode_command))
    app.add_handler(CommandHandler("universe",       universe_command))
    app.add_handler(CommandHandler("ritual",         ritual_command))
    app.add_handler(CommandHandler("duality",        duality_command))
    app.add_handler(CommandHandler("glitch",         glitch_command))
    app.add_handler(CommandHandler("nightreport",    nightreport_command))
    app.add_handler(CommandHandler("sigil",          sigil_command))

    # ── Aesthetic ORIGINAL (handlers/aesthetic.py) ────────────────────────
    app.add_handler(CommandHandler("tarot",          aesthetic.tarot))
    app.add_handler(CommandHandler("fate",           aesthetic.fate))
    app.add_handler(CommandHandler("whisper",        aesthetic.whisper))
    app.add_handler(CommandHandler("lore",           aesthetic.lore))
    app.add_handler(CommandHandler("starsign",       aesthetic.starsign))
    app.add_handler(CommandHandler("confess",        aesthetic.confess))
    app.add_handler(CommandHandler("moodboard",      aesthetic.moodboard))
    app.add_handler(CommandHandler("dream",          aesthetic.dream))
    app.add_handler(CommandHandler("manifest",       aesthetic.manifest))
    app.add_handler(CommandHandler("emojiaura",      aesthetic.emoji_aura))

    # ── Mines (oracle_mines.py) ───────────────────────────────────────────
    app.add_handler(CommandHandler("mines",          mines_command))
    for h in get_mines_handlers():
        app.add_handler(h)

    # ── Solo Bet (oracle_solobet.py) ──────────────────────────────────────
    app.add_handler(CommandHandler("bet",            bet_command))
    app.add_handler(CommandHandler("betstats",       betstats_command))
    app.add_handler(CommandHandler("topbet",         topbet_command))

    # ── Wallet (oracle_wallet.py) ─────────────────────────────────────────
    app.add_handler(CommandHandler("wallet",         wallet_command))
    app.add_handler(CommandHandler("deposit",        deposit_command))
    app.add_handler(CommandHandler("withdraw",       withdraw_command))
    app.add_handler(CommandHandler("setpass",        setpass_command))
    app.add_handler(CommandHandler("changepass",     changepass_command))
    app.add_handler(CommandHandler("recover",        recover_command))

    # ── Games (handlers/games.py) ─────────────────────────────────────────
    app.add_handler(CommandHandler("quiz",           games.quiz))
    app.add_handler(CommandHandler("truth",          games.truth))
    app.add_handler(CommandHandler("dare",           games.dare))
    app.add_handler(CommandHandler("wyr",            games.would_you_rather))
    app.add_handler(CommandHandler("nhie",           games.never_have_i_ever))
    app.add_handler(CommandHandler("rps",            games.rock_paper_scissors))
    app.add_handler(CommandHandler("riddle",         games.riddle))
    app.add_handler(CommandHandler("riddleanswer",   games.riddle_answer))
    app.add_handler(CommandHandler("scramble",       games.scramble))
    app.add_handler(CommandHandler("unscramble",     games.unscramble))
    app.add_handler(CommandHandler("guess",          games.guess_number))
    app.add_handler(CommandHandler("leaderboard",    games.leaderboard_cmd))
    app.add_handler(CommandHandler("dice",           games.dice_game))
    app.add_handler(CommandHandler("darts",          games.darts_game))
    app.add_handler(CommandHandler("basketball",     games.basketball_game))
    app.add_handler(CommandHandler("bowling",        games.bowling_game))
    app.add_handler(CommandHandler("football",       games.football_game))
    app.add_handler(CommandHandler("slot",           games.slot_game))
    app.add_handler(CommandHandler("hangman",        games.hangman))
    app.add_handler(CommandHandler("hangmanguess",   games.hangman_guess))
    app.add_handler(CommandHandler("tictactoe",      games.tictactoe))
    app.add_handler(CommandHandler("ttt",            games.ttt_move))
    app.add_handler(CommandHandler("wordchain",      games.wordchain_start))
    app.add_handler(CommandHandler("chainword",      games.chain_word))
    app.add_handler(CommandHandler("trivia",         games.trivia_category))
    app.add_handler(CommandHandler("wordle",         games.wordle))
    app.add_handler(CommandHandler("wordleguess",    games.wordle_guess))

    # ── Moderation (handlers/moderation.py) ───────────────────────────────
    app.add_handler(CommandHandler("mute",           moderation.mute))
    app.add_handler(CommandHandler("unmute",         moderation.unmute))
    app.add_handler(CommandHandler("ban",            moderation.ban))
    app.add_handler(CommandHandler("kick",           moderation.kick))
    app.add_handler(CommandHandler("warn",           moderation.warn))
    app.add_handler(CommandHandler("rules",          moderation.show_rules))
    app.add_handler(CommandHandler("warnings",       moderation.check_warnings))
    app.add_handler(CommandHandler("clearwarns",     moderation.clear_warnings))
    app.add_handler(CommandHandler("pin",            moderation.pin))
    app.add_handler(CommandHandler("unpin",          moderation.unpin))
    app.add_handler(CommandHandler("purge",          moderation.purge))
    app.add_handler(CommandHandler("setrules",       moderation.set_rules))
    app.add_handler(CommandHandler("lock",           moderation.lock))
    app.add_handler(CommandHandler("unlock",         moderation.unlock))

    # ── Stats (handlers/stats.py) ─────────────────────────────────────────
    app.add_handler(CommandHandler("stats",          stats.stats))
    app.add_handler(CommandHandler("topactive",      stats.top_active))
    app.add_handler(CommandHandler("msgcount",       stats.msg_count))

    # ── Economy (handlers/economy.py) ─────────────────────────────────────
    app.add_handler(CommandHandler("daily",          economy.daily))
    app.add_handler(CommandHandler("balance",        economy.balance))
    app.add_handler(CommandHandler("gamble",         economy.gamble))
    app.add_handler(CommandHandler("richest",        economy.economy_leaderboard))

    # ── Marriage / Shop (handlers/marriage.py) ────────────────────────────
    app.add_handler(CommandHandler("marry",          marriage.marry))
    app.add_handler(CommandHandler("accept",         marriage.accept))
    app.add_handler(CommandHandler("divorce",        marriage.divorce))
    app.add_handler(CommandHandler("profile",        marriage.profile))
    app.add_handler(CommandHandler("work",           marriage.work))
    app.add_handler(CommandHandler("chests",         marriage.chests))
    app.add_handler(CommandHandler("shop",           marriage.shop))
    app.add_handler(CommandHandler("buy",            marriage.buy))
    app.add_handler(CommandHandler("inventory",      marriage.inventory))
    app.add_handler(CommandHandler("gift",           marriage.gift))
    app.add_handler(CommandHandler("settings",       marriage.settings))

    # ── Death Games (handlers/deathgames.py) ──────────────────────────────
    app.add_handler(CommandHandler("survive",        deathgames.survive))
    app.add_handler(CommandHandler("revive",         deathgames.revive))
    app.add_handler(CommandHandler("deathstatus",    deathgames.deathstatus))
    app.add_handler(CommandHandler("roulette",       deathgames.roulette))
    app.add_handler(CommandHandler("deathgame",      deathgames.deathgame))
    app.add_handler(CommandHandler("joingame",       deathgames.joingame))
    app.add_handler(CommandHandler("startround",     deathgames.startround))
    app.add_handler(CommandHandler("kill",           deathgames.kill))
    app.add_handler(CommandHandler("vote",           deathgames.vote))
    app.add_handler(CommandHandler("endgame",        deathgames.endgame))

    # ── Utility (handlers/utility.py) ─────────────────────────────────────
    app.add_handler(CommandHandler("id",             utility.get_id))
    app.add_handler(CommandHandler("info",           utility.user_info))
    app.add_handler(CommandHandler("remind",         utility.remind))
    app.add_handler(CommandHandler("groupinfo",      utility.group_info))
    app.add_handler(CommandHandler("afk",            utility.set_afk))
    app.add_handler(CommandHandler("report",         utility.report))

    # ── Friendship (handlers/friendship.py) ───────────────────────────────
    app.add_handler(CommandHandler("bestie",         friendship.bestie))
    app.add_handler(CommandHandler("duo",            friendship.duo))
    app.add_handler(CommandHandler("friendship",     friendship.friendship_score))
    app.add_handler(CommandHandler("tagbestie",      friendship.tag_bestie))
    app.add_handler(CommandHandler("squad",          friendship.squad))
    app.add_handler(CommandHandler("loyalty",        friendship.loyalty))
    app.add_handler(CommandHandler("ship",           friendship.ship))
    app.add_handler(CommandHandler("randomship",     friendship.random_ship))
    app.add_handler(CommandHandler("matchmaker",     friendship.matchmaker))
    app.add_handler(CommandHandler("friendshiptest", friendship.friendship_test))
    app.add_handler(CommandHandler("hug",            friendship.hug))
    app.add_handler(CommandHandler("pat",            friendship.pat))
    app.add_handler(CommandHandler("highfive",       friendship.highfive))
    app.add_handler(CommandHandler("slap",           friendship.slap))
    app.add_handler(CommandHandler("kiss",           friendship.kiss))
    app.add_handler(CommandHandler("poke",           friendship.poke))
    app.add_handler(CommandHandler("cuddle",         friendship.cuddle))
    app.add_handler(CommandHandler("wave",           friendship.wave))
    app.add_handler(CommandHandler("bite",           friendship.bite))
    app.add_handler(CommandHandler("tickle",         friendship.tickle))

    # ── Fun (handlers/fun.py) ─────────────────────────────────────────────
    app.add_handler(CommandHandler("roast",          fun.roast))
    app.add_handler(CommandHandler("compliment",     fun.compliment))
    app.add_handler(CommandHandler("8ball",          fun.eight_ball))
    app.add_handler(CommandHandler("vibe",           fun.vibe))
    app.add_handler(CommandHandler("quote",          fun.quote))
    app.add_handler(CommandHandler("poll",           fun.poll))
    app.add_handler(CommandHandler("rank",           fun.rank))
    app.add_handler(CommandHandler("ratethis",       fun.rate_this))
    app.add_handler(CommandHandler("impostor",       fun.impostor_start))
    app.add_handler(CommandHandler("revealimpostor", fun.impostor_reveal))

    # ── Matchmaking (handlers/matchmaking.py) ─────────────────────────────
    app.add_handler(CommandHandler("crush",          matchmaking.set_crush))
    app.add_handler(CommandHandler("clearcrush",     matchmaking.clear_crush))
    app.add_handler(CommandHandler("secretadmirer",  matchmaking.secret_admirer))

    # ── Events / Welcome (handlers/events.py) ─────────────────────────────
    app.add_handler(CommandHandler("setwelcome",     events.set_welcome))
    app.add_handler(CommandHandler("setgoodbye",     events.set_goodbye))
    app.add_handler(CommandHandler("invite",         events.get_invite))
    app.add_handler(CommandHandler("joined",         events.show_joined))
    app.add_handler(CommandHandler("left",           events.show_left))
    app.add_handler(ChatMemberHandler(events.on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # ── Time Capsule (handlers/timecapsule.py) ────────────────────────────
    app.add_handler(CommandHandler("timecapsule",    timecapsule.timecapsule))
    app.add_handler(CommandHandler("capsules",       timecapsule.list_capsules))

    # ── Scheduled jobs (weekly summary etc.) ─────────────────────────────
    if GROUP_CHAT_ID:
        register_event_jobs(app, GROUP_CHAT_ID)
        logger.info("✅ Oracle scheduled jobs registered for chat %d", GROUP_CHAT_ID)
    else:
        logger.warning(
            "⚠️  GROUP_CHAT_ID not set — weekly summary disabled. "
            "Add it to Render Environment variables."
        )

    # ── Webhook ───────────────────────────────────────────────────────────
    webhook_path     = TOKEN
    full_webhook_url = f"{RENDER_EXTERNAL_URL}/{webhook_path}"
    logger.info("🌙 Starting Midnight Oracle webhook at %s", full_webhook_url)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=full_webhook_url,
    )


if __name__ == "__main__":
    main()
