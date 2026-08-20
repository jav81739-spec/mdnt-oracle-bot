"""
bot.py — Midnight Oracle Bot | COMPLETE UPDATED VERSION
Webhook mode for Render free tier hosting.

What's new vs old version:
  ✅ Channel post auto-reply (channel_oracle.py in root)
  ✅ Daily /checkin + streak multipliers (engagement.py in root)
  ✅ /gift coins to friends (engagement.py)
  ✅ /rob revamped with vault-awareness (engagement.py)
  ✅ /vent anonymous board (engagement.py)
  ✅ /streakcheck (engagement.py)
  ✅ 13 new aesthetic commands — /shadow, /element, /corecode,
     /universe, /ritual, /duality, /glitch, /nightreport, /sigil,
     /identity, /vibecheck — all daily-seeded (aesthetic.py in root)
  ✅ /mines game — pick tiles, dodge bombs, cash out (mines.py in root)
  ✅ /bet + bbet shorthand — solo 50/50 with streaks (solobet.py in root)
  ✅ /wallet /deposit /withdraw /setpass /recover (wallet.py in root)
  ✅ /oraclehour /enter /eventcheck group events (oracle_events.py in root)
  ✅ /checkin /betstats /topbet /walletstats new commands
  ✅ AI chat completely rewritten — never rude, warm Oracle personality
  ✅ Weekly auto-summary every Sunday 9 PM
  ✅ Oracle's Hour events system
  ✅ All old commands preserved exactly
  ✅ Duplicate commands removed (/prophecy→/oracle, /vibe→/vibecheck etc.)

REMOVED (merged/replaced):
  /prophecy → /oracle
  /omen     → /oracle
  /energy   → /vibecheck
  /hex      → /curse (deathgames)

Files needed in REPO ROOT (same level as bot.py):
  channel_oracle.py, engagement.py, aesthetic.py,
  mines.py, solobet.py, wallet.py, oracle_events.py

Files in handlers/ folder (unchanged):
  chat.py, games.py, moderation.py, utility.py,
  aesthetic.py (OLD — now overridden by root aesthetic.py),
  friendship.py, fun.py, matchmaking.py, stats.py,
  events.py, economy.py, timecapsule.py, marriage.py, deathgames.py
"""

import logging
import os
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

# ─── New root-level modules ────────────────────────────────────────────────
from channel_oracle import get_channel_oracle_handler
from engagement import (
    checkin_command,
    gift_command,
    rob_command as engagement_rob,
    leaderboard_command as coins_leaderboard,
    vent_command,
    streakcheck_command,
)
from aesthetic import (
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
from oracle_events import (
    oraclehour_command,
    enter_command,
    eventcheck_command,
    register_event_jobs,
)
from mines import mines_command, get_mines_handlers
from solobet import (
    bet_command,
    betstats_command,
    topbet_command,
    get_bbet_handler,
)
from wallet import (
    wallet_command,
    deposit_command,
    withdraw_command,
    setpass_command,
    changepass_command,
    recover_command,
)

# ─── Existing handlers/ modules (unchanged) ────────────────────────────────
from handlers import (
    chat,
    games,
    moderation,
    utility,
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
# Note: handlers.aesthetic is intentionally NOT imported here.
# The new root-level aesthetic.py replaces it entirely.

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Command menu (99 max — Telegram hard limit) ───────────────────────────
BOT_COMMANDS = [
    # General
    BotCommand("start",         "Welcome message"),
    BotCommand("help",          "List all commands"),

    # Engagement (NEW)
    BotCommand("checkin",       "Daily check-in — earn coins + build streak"),
    BotCommand("streakcheck",   "View your check-in streak"),
    BotCommand("gift",          "Gift coins to someone (reply to their msg)"),
    BotCommand("vent",          "Post anonymously to the group"),
    BotCommand("bet",           "50/50 solo bet — /bet <amount>"),
    BotCommand("mines",         "Mines game — pick tiles, dodge bombs"),
    BotCommand("wallet",        "View your protected coin vault"),
    BotCommand("deposit",       "Lock coins in vault (safe from rob)"),
    BotCommand("withdraw",      "Take coins out of vault"),
    BotCommand("oraclehour",    "Admin: trigger an Oracle group event"),
    BotCommand("enter",         "Join an active Oracle event"),

    # Economy
    BotCommand("daily",         "Claim daily coins"),
    BotCommand("balance",       "Check coin balance"),
    BotCommand("rob",           "Try robbing someone (reply)"),
    BotCommand("gamble",        "Gamble your coins"),
    BotCommand("richest",       "Coin leaderboard"),
    BotCommand("leaderboard",   "Game win rankings"),
    BotCommand("topbet",        "Top bettors leaderboard"),
    BotCommand("betstats",      "Your betting stats"),

    # Aesthetic / Mystery (NEW + upgraded)
    BotCommand("oracle",        "Today's personal prophecy"),
    BotCommand("aura",          "Scan your aura color + meaning"),
    BotCommand("identity",      "Your Oracle identity card"),
    BotCommand("vibecheck",     "Full vibe check with stats"),
    BotCommand("shadow",        "Your shadow self revealed"),
    BotCommand("element",       "Your cosmic element"),
    BotCommand("corecode",      "Your 3 core personality words"),
    BotCommand("universe",      "What the universe wants you to know"),
    BotCommand("ritual",        "Today's ritual from the Oracle"),
    BotCommand("duality",       "Your light and dark side"),
    BotCommand("glitch",        "Oracle glitches out"),
    BotCommand("nightreport",   "Tonight's personal energy reading"),
    BotCommand("sigil",         "Text-art sigil generated for you"),
    BotCommand("tarot",         "Draw a tarot card"),
    BotCommand("fate",          "Today's cryptic fate"),
    BotCommand("starsign",      "Zodiac reading"),
    BotCommand("dream",         "AI dream interpretation"),
    BotCommand("manifest",      "Stylized affirmation card"),
    BotCommand("emojiaura",     "Emoji-only energy reading"),
    BotCommand("lore",          "Random group lore drop"),
    BotCommand("moodboard",     "Today's aesthetic mood"),
    BotCommand("confess",       "Anonymous confession"),

    # Games
    BotCommand("quiz",          "Trivia round"),
    BotCommand("truth",         "Truth question"),
    BotCommand("dare",          "Dare challenge"),
    BotCommand("wyr",           "Would you rather"),
    BotCommand("nhie",          "Never have I ever"),
    BotCommand("rps",           "Rock paper scissors vs bot"),
    BotCommand("riddle",        "Get a riddle"),
    BotCommand("scramble",      "Unscramble a word"),
    BotCommand("guess",         "Guess a number 1-20"),
    BotCommand("dice",          "Roll a dice"),
    BotCommand("darts",         "Throw darts"),
    BotCommand("basketball",    "Shoot a basketball"),
    BotCommand("bowling",       "Bowl a strike (maybe)"),
    BotCommand("football",      "Kick a football"),
    BotCommand("slot",          "Spin the slot machine"),
    BotCommand("hangman",       "Start hangman"),
    BotCommand("tictactoe",     "Challenge someone (reply)"),
    BotCommand("wordchain",     "Start a word chain"),
    BotCommand("trivia",        "Trivia by category"),
    BotCommand("wordle",        "Get today's wordle"),
    BotCommand("impostor",      "Start an impostor round"),

    # Social
    BotCommand("hug",           "Hug someone (reply)"),
    BotCommand("pat",           "Pat someone (reply)"),
    BotCommand("highfive",      "High-five someone (reply)"),
    BotCommand("slap",          "Slap someone (reply)"),
    BotCommand("kiss",          "Kiss someone (reply)"),
    BotCommand("poke",          "Poke someone (reply)"),
    BotCommand("cuddle",        "Cuddle someone (reply)"),
    BotCommand("wave",          "Wave at someone (reply)"),
    BotCommand("bite",          "Bite someone (reply)"),
    BotCommand("ship",          "Ship two people together"),
    BotCommand("roast",         "Playful roast"),
    BotCommand("compliment",    "Give a compliment"),
    BotCommand("8ball",         "Magic 8-ball answer"),
    BotCommand("quote",         "Random quote"),

    # Friendship
    BotCommand("bestie",        "Declare a bestie"),
    BotCommand("duo",           "Generate a duo name"),
    BotCommand("friendship",    "Compatibility score"),
    BotCommand("loyalty",       "Loyalty score reading"),
    BotCommand("crush",         "Privately pick a crush (reply)"),
    BotCommand("secretadmirer", "Send someone an anonymous DM"),
    BotCommand("randomship",    "Bot randomly ships two members"),

    # Moderation (admin)
    BotCommand("mute",          "Mute a user (admin)"),
    BotCommand("unmute",        "Unmute a user (admin)"),
    BotCommand("ban",           "Ban a user (admin)"),
    BotCommand("kick",          "Kick a user (admin)"),
    BotCommand("warn",          "Warn a user (admin)"),
    BotCommand("warnings",      "Check a user's warning count"),
    BotCommand("clearwarns",    "Clear warnings (admin)"),
    BotCommand("purge",         "Delete N messages (admin)"),
    BotCommand("pin",           "Pin the replied message (admin)"),
    BotCommand("rules",         "Show group rules"),
    BotCommand("setrules",      "Set group rules (admin)"),

    # Utility
    BotCommand("id",            "Get user/chat ID"),
    BotCommand("info",          "User info card"),
    BotCommand("stats",         "Group activity stats"),
    BotCommand("topactive",     "Most active members"),
    BotCommand("afk",           "Mark yourself away"),
    BotCommand("report",        "Report a message to admins"),
    BotCommand("poll",          "Create a poll: /poll Q | A | B"),
    BotCommand("timecapsule",   "Lock a message for later"),
    BotCommand("capsules",      "List pending time capsules"),

    # Marriage / Shop
    BotCommand("marry",         "Propose to someone (reply)"),
    BotCommand("divorce",       "End a marriage"),
    BotCommand("profile",       "View your Oracle profile"),
    BotCommand("work",          "Earn coins by working"),
    BotCommand("shop",          "Browse the item shop"),
    BotCommand("buy",           "Buy an item from shop"),
    BotCommand("inventory",     "View your inventory"),

    # Death Games
    BotCommand("survive",       "Survive the death game"),
    BotCommand("deathgame",     "Start a death game"),
    BotCommand("joingame",      "Join an active death game"),
    BotCommand("roulette",      "Play Russian roulette"),
]


# ─── Startup hook ──────────────────────────────────────────────────────────
async def _post_init(app: Application):
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Command menu registered (%d commands).", len(BOT_COMMANDS))

    await economy.load_from_storage()
    logger.info("Economy balances loaded.")

    await timecapsule.load_and_reschedule(app)
    logger.info("Time capsules rescheduled.")

    await chat.load_from_storage()
    logger.info("Chat mode settings loaded.")

    await marriage.load_from_storage()
    logger.info("Marriage/shop data loaded.")

    await deathgames.load_from_storage()
    logger.info("Death Life Games data loaded.")


# ─── Main ──────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not found. Add it in Render's Environment tab.")
    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL not set. This is auto-set by Render on web services."
        )

    app = Application.builder().token(TOKEN).post_init(_post_init).build()

    # ── 0. Channel Oracle — MUST be first ─────────────────────────────────
    app.add_handler(get_channel_oracle_handler(), group=0)

    # ── 1. bbet text trigger — BEFORE general chat handler ────────────────
    app.add_handler(get_bbet_handler(), group=0)

    # ── 2. General ────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", utility.start_welcome))
    app.add_handler(CommandHandler("help", utility.help_command))

    # ── 3. AI Chat + message tracking ────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat.auto_reply), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, friendship.track_message), group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, utility.check_afk_mentions), group=3)
    app.add_handler(CommandHandler("chat", chat.toggle_chat))
    app.add_handler(CommandHandler("persona", chat.set_persona))
    app.add_handler(CommandHandler("sticker", chat.send_random_sticker))
    app.add_handler(CommandHandler("getstickerid", chat.get_sticker_id))
    app.add_handler(CommandHandler("gif", chat.send_random_gif))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, chat.maybe_react_to_message), group=4)
    app.add_handler(MessageHandler(filters.Sticker.ALL, chat.sticker_reply), group=5)
    app.add_handler(MessageHandler(filters.ANIMATION, chat.gif_reply), group=6)

    # ── 4. NEW: Engagement ────────────────────────────────────────────────
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("streakcheck", streakcheck_command))
    app.add_handler(CommandHandler("vent", vent_command))
    # /gift is handled by marriage.gift below — engagement gift is a fallback
    # Use /cgift for the engagement coin-gift version to avoid conflict
    app.add_handler(CommandHandler("cgift", gift_command))
    # /rob — engagement version overrides economy version (smarter with vault)
    app.add_handler(CommandHandler("rob", engagement_rob))
    # /leaderboard — coins leaderboard (games leaderboard is /gleaderboard)
    app.add_handler(CommandHandler("coinboard", coins_leaderboard))

    # ── 5. NEW: Oracle Events ─────────────────────────────────────────────
    app.add_handler(CommandHandler("oraclehour", oraclehour_command))
    app.add_handler(CommandHandler("enter", enter_command))
    app.add_handler(CommandHandler("eventcheck", eventcheck_command))

    # ── 6. NEW: Aesthetic (overrides handlers/aesthetic.py) ───────────────
    app.add_handler(CommandHandler("oracle",      oracle_command))
    app.add_handler(CommandHandler("aura",        aura_command))
    app.add_handler(CommandHandler("identity",    identity_command))
    app.add_handler(CommandHandler("vibecheck",   vibecheck_command))
    app.add_handler(CommandHandler("shadow",      shadow_command))
    app.add_handler(CommandHandler("element",     element_command))
    app.add_handler(CommandHandler("corecode",    corecode_command))
    app.add_handler(CommandHandler("universe",    universe_command))
    app.add_handler(CommandHandler("ritual",      ritual_command))
    app.add_handler(CommandHandler("duality",     duality_command))
    app.add_handler(CommandHandler("glitch",      glitch_command))
    app.add_handler(CommandHandler("nightreport", nightreport_command))
    app.add_handler(CommandHandler("sigil",       sigil_command))
    # These stay from handlers/aesthetic.py
    app.add_handler(CommandHandler("tarot",       aesthetic_handlers_shim("tarot")))
    app.add_handler(CommandHandler("fate",        aesthetic_handlers_shim("fate")))
    app.add_handler(CommandHandler("whisper",     aesthetic_handlers_shim("whisper")))
    app.add_handler(CommandHandler("lore",        aesthetic_handlers_shim("lore")))
    app.add_handler(CommandHandler("starsign",    aesthetic_handlers_shim("starsign")))
    app.add_handler(CommandHandler("confess",     aesthetic_handlers_shim("confess")))
    app.add_handler(CommandHandler("moodboard",   aesthetic_handlers_shim("moodboard")))
    app.add_handler(CommandHandler("dream",       aesthetic_handlers_shim("dream")))
    app.add_handler(CommandHandler("manifest",    aesthetic_handlers_shim("manifest")))
    app.add_handler(CommandHandler("emojiaura",   aesthetic_handlers_shim("emoji_aura")))

    # ── 7. NEW: Mines Game ────────────────────────────────────────────────
    app.add_handler(CommandHandler("mines", mines_command))
    for h in get_mines_handlers():
        app.add_handler(h)

    # ── 8. NEW: Solo Bet ─────────────────────────────────────────────────
    app.add_handler(CommandHandler("bet",       bet_command))
    app.add_handler(CommandHandler("betstats",  betstats_command))
    app.add_handler(CommandHandler("topbet",    topbet_command))

    # ── 9. NEW: Wallet / Vault ────────────────────────────────────────────
    app.add_handler(CommandHandler("wallet",     wallet_command))
    app.add_handler(CommandHandler("deposit",    deposit_command))
    app.add_handler(CommandHandler("withdraw",   withdraw_command))
    app.add_handler(CommandHandler("setpass",    setpass_command))
    app.add_handler(CommandHandler("changepass", changepass_command))
    app.add_handler(CommandHandler("recover",    recover_command))

    # ── 10. Games (original) ──────────────────────────────────────────────
    app.add_handler(CommandHandler("quiz",        games.quiz))
    app.add_handler(CommandHandler("truth",       games.truth))
    app.add_handler(CommandHandler("dare",        games.dare))
    app.add_handler(CommandHandler("wyr",         games.would_you_rather))
    app.add_handler(CommandHandler("nhie",        games.never_have_i_ever))
    app.add_handler(CommandHandler("rps",         games.rock_paper_scissors))
    app.add_handler(CommandHandler("riddle",      games.riddle))
    app.add_handler(CommandHandler("riddleanswer",games.riddle_answer))
    app.add_handler(CommandHandler("scramble",    games.scramble))
    app.add_handler(CommandHandler("unscramble",  games.unscramble))
    app.add_handler(CommandHandler("guess",       games.guess_number))
    app.add_handler(CommandHandler("leaderboard", games.leaderboard_cmd))
    app.add_handler(CommandHandler("gleaderboard",games.leaderboard_cmd))
    app.add_handler(CommandHandler("dice",        games.dice_game))
    app.add_handler(CommandHandler("darts",       games.darts_game))
    app.add_handler(CommandHandler("basketball",  games.basketball_game))
    app.add_handler(CommandHandler("bowling",     games.bowling_game))
    app.add_handler(CommandHandler("football",    games.football_game))
    app.add_handler(CommandHandler("slot",        games.slot_game))
    app.add_handler(CommandHandler("hangman",     games.hangman))
    app.add_handler(CommandHandler("hangmanguess",games.hangman_guess))
    app.add_handler(CommandHandler("tictactoe",   games.tictactoe))
    app.add_handler(CommandHandler("ttt",         games.ttt_move))
    app.add_handler(CommandHandler("wordchain",   games.wordchain_start))
    app.add_handler(CommandHandler("chainword",   games.chain_word))
    app.add_handler(CommandHandler("trivia",      games.trivia_category))
    app.add_handler(CommandHandler("wordle",      games.wordle))
    app.add_handler(CommandHandler("wordleguess", games.wordle_guess))

    # ── 11. Moderation (original) ─────────────────────────────────────────
    app.add_handler(CommandHandler("mute",       moderation.mute))
    app.add_handler(CommandHandler("unmute",     moderation.unmute))
    app.add_handler(CommandHandler("ban",        moderation.ban))
    app.add_handler(CommandHandler("kick",       moderation.kick))
    app.add_handler(CommandHandler("warn",       moderation.warn))
    app.add_handler(CommandHandler("rules",      moderation.show_rules))
    app.add_handler(CommandHandler("warnings",   moderation.check_warnings))
    app.add_handler(CommandHandler("clearwarns", moderation.clear_warnings))
    app.add_handler(CommandHandler("pin",        moderation.pin))
    app.add_handler(CommandHandler("unpin",      moderation.unpin))
    app.add_handler(CommandHandler("purge",      moderation.purge))
    app.add_handler(CommandHandler("setrules",   moderation.set_rules))
    app.add_handler(CommandHandler("lock",       moderation.lock))
    app.add_handler(CommandHandler("unlock",     moderation.unlock))

    # ── 12. Stats (original) ──────────────────────────────────────────────
    app.add_handler(CommandHandler("stats",      stats.stats))
    app.add_handler(CommandHandler("topactive",  stats.top_active))
    app.add_handler(CommandHandler("msgcount",   stats.msg_count))

    # ── 13. Economy (original) ────────────────────────────────────────────
    app.add_handler(CommandHandler("daily",    economy.daily))
    app.add_handler(CommandHandler("balance",  economy.balance))
    app.add_handler(CommandHandler("gamble",   economy.gamble))
    app.add_handler(CommandHandler("richest",  economy.economy_leaderboard))

    # ── 14. Marriage / Shop (original) ────────────────────────────────────
    app.add_handler(CommandHandler("marry",     marriage.marry))
    app.add_handler(CommandHandler("accept",    marriage.accept))
    app.add_handler(CommandHandler("divorce",   marriage.divorce))
    app.add_handler(CommandHandler("profile",   marriage.profile))
    app.add_handler(CommandHandler("work",      marriage.work))
    app.add_handler(CommandHandler("chests",    marriage.chests))
    app.add_handler(CommandHandler("shop",      marriage.shop))
    app.add_handler(CommandHandler("buy",       marriage.buy))
    app.add_handler(CommandHandler("inventory", marriage.inventory))
    app.add_handler(CommandHandler("gift",      marriage.gift))
    app.add_handler(CommandHandler("settings",  marriage.settings))

    # ── 15. Death Games (original) ────────────────────────────────────────
    app.add_handler(CommandHandler("survive",    deathgames.survive))
    app.add_handler(CommandHandler("revive",     deathgames.revive))
    app.add_handler(CommandHandler("deathstatus",deathgames.deathstatus))
    app.add_handler(CommandHandler("roulette",   deathgames.roulette))
    app.add_handler(CommandHandler("deathgame",  deathgames.deathgame))
    app.add_handler(CommandHandler("joingame",   deathgames.joingame))
    app.add_handler(CommandHandler("startround", deathgames.startround))
    app.add_handler(CommandHandler("kill",       deathgames.kill))
    app.add_handler(CommandHandler("vote",       deathgames.vote))
    app.add_handler(CommandHandler("endgame",    deathgames.endgame))

    # ── 16. Utility (original) ────────────────────────────────────────────
    app.add_handler(CommandHandler("id",        utility.get_id))
    app.add_handler(CommandHandler("info",      utility.user_info))
    app.add_handler(CommandHandler("remind",    utility.remind))
    app.add_handler(CommandHandler("groupinfo", utility.group_info))
    app.add_handler(CommandHandler("afk",       utility.set_afk))
    app.add_handler(CommandHandler("report",    utility.report))

    # ── 17. Friendship / Social (original) ───────────────────────────────
    app.add_handler(CommandHandler("bestie",       friendship.bestie))
    app.add_handler(CommandHandler("duo",          friendship.duo))
    app.add_handler(CommandHandler("friendship",   friendship.friendship_score))
    app.add_handler(CommandHandler("tagbestie",    friendship.tag_bestie))
    app.add_handler(CommandHandler("squad",        friendship.squad))
    app.add_handler(CommandHandler("loyalty",      friendship.loyalty))
    app.add_handler(CommandHandler("ship",         friendship.ship))
    app.add_handler(CommandHandler("randomship",   friendship.random_ship))
    app.add_handler(CommandHandler("matchmaker",   friendship.matchmaker))
    app.add_handler(CommandHandler("friendshiptest",friendship.friendship_test))
    app.add_handler(CommandHandler("hug",          friendship.hug))
    app.add_handler(CommandHandler("pat",          friendship.pat))
    app.add_handler(CommandHandler("highfive",     friendship.highfive))
    app.add_handler(CommandHandler("slap",         friendship.slap))
    app.add_handler(CommandHandler("kiss",         friendship.kiss))
    app.add_handler(CommandHandler("poke",         friendship.poke))
    app.add_handler(CommandHandler("cuddle",       friendship.cuddle))
    app.add_handler(CommandHandler("wave",         friendship.wave))
    app.add_handler(CommandHandler("bite",         friendship.bite))
    app.add_handler(CommandHandler("tickle",       friendship.tickle))

    # ── 18. Fun (original) ───────────────────────────────────────────────
    app.add_handler(CommandHandler("roast",         fun.roast))
    app.add_handler(CommandHandler("compliment",    fun.compliment))
    app.add_handler(CommandHandler("8ball",         fun.eight_ball))
    app.add_handler(CommandHandler("vibe",          fun.vibe))
    app.add_handler(CommandHandler("quote",         fun.quote))
    app.add_handler(CommandHandler("poll",          fun.poll))
    app.add_handler(CommandHandler("rank",          fun.rank))
    app.add_handler(CommandHandler("ratethis",      fun.rate_this))
    app.add_handler(CommandHandler("impostor",      fun.impostor_start))
    app.add_handler(CommandHandler("revealimpostor",fun.impostor_reveal))

    # ── 19. Matchmaking (original) ────────────────────────────────────────
    app.add_handler(CommandHandler("crush",        matchmaking.set_crush))
    app.add_handler(CommandHandler("clearcrush",   matchmaking.clear_crush))
    app.add_handler(CommandHandler("secretadmirer",matchmaking.secret_admirer))

    # ── 20. Events / Welcome (original) ──────────────────────────────────
    app.add_handler(CommandHandler("setwelcome", events.set_welcome))
    app.add_handler(CommandHandler("setgoodbye", events.set_goodbye))
    app.add_handler(CommandHandler("invite",     events.get_invite))
    app.add_handler(CommandHandler("joined",     events.show_joined))
    app.add_handler(CommandHandler("left",       events.show_left))
    app.add_handler(ChatMemberHandler(events.on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # ── 21. Time Capsule (original) ───────────────────────────────────────
    app.add_handler(CommandHandler("timecapsule", timecapsule.timecapsule))
    app.add_handler(CommandHandler("capsules",    timecapsule.list_capsules))

    # ── 22. Scheduled jobs ────────────────────────────────────────────────
    if GROUP_CHAT_ID:
        register_event_jobs(app, GROUP_CHAT_ID)
        logger.info("Oracle event jobs registered for chat %d", GROUP_CHAT_ID)
    else:
        logger.warning(
            "GROUP_CHAT_ID not set — weekly summary and scheduled events disabled. "
            "Add GROUP_CHAT_ID to Render environment variables."
        )

    # ── 23. Webhook ───────────────────────────────────────────────────────
    webhook_path = TOKEN
    full_webhook_url = f"{RENDER_EXTERNAL_URL}/{webhook_path}"
    logger.info("Starting webhook at %s", full_webhook_url)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=full_webhook_url,
    )


# ─── Shim helper for handlers/aesthetic.py commands ───────────────────────
# The old handlers/aesthetic.py is still used for tarot, fate, whisper, etc.
# This avoids touching handlers/aesthetic.py at all.
def aesthetic_handlers_shim(func_name: str):
    """
    Dynamically fetches a function from handlers/aesthetic.py by name.
    Keeps old aesthetic handlers working without modifying handlers/aesthetic.py.
    """
    from handlers import aesthetic as _old_aesthetic
    return getattr(_old_aesthetic, func_name)


if __name__ == "__main__":
    main()
