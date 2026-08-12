"""
Main entry point for the bot — WEBHOOK MODE.
Run with: python bot.py

Requires these environment variables set on Render:
  BOT_TOKEN         - from @BotFather
  GEMINI_API_KEY    - optional, for AI chat replies
  RENDER_EXTERNAL_URL is set automatically by Render — no action needed.

Why webhooks instead of polling:
Render's free tier spins the whole service down after ~15 min of no
incoming HTTP requests. Polling mode (`app.run_polling()`) only makes
OUTGOING requests to Telegram, so Render never sees an incoming request
to justify keeping it awake, and the bot goes silent.
Webhook mode has Telegram push new messages TO your server as an
incoming HTTP request — which both delivers the message AND wakes
Render up if it was asleep. This is the correct setup for free hosting.
"""
import logging
import os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, filters

from handlers import chat, games, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Render sets this automatically for every web service, e.g.
# https://your-service-name.onrender.com
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# This list populates the "/" autocomplete menu in Telegram.
BOT_COMMANDS = [
    BotCommand("start", "Welcome message"),
    BotCommand("help", "List all commands"),
    BotCommand("chat", "Toggle AI chat mode"),
    BotCommand("persona", "Set bot personality"),
    BotCommand("quiz", "Trivia round"),
    BotCommand("truth", "Truth question"),
    BotCommand("dare", "Dare challenge"),
    BotCommand("wyr", "Would you rather"),
    BotCommand("nhie", "Never have I ever"),
    BotCommand("rps", "Rock paper scissors vs bot"),
    BotCommand("riddle", "Get a riddle"),
    BotCommand("scramble", "Unscramble a word"),
    BotCommand("guess", "Guess a number 1-20"),
    BotCommand("leaderboard", "Show game win rankings"),
    BotCommand("dice", "Roll a dice"),
    BotCommand("darts", "Throw darts"),
    BotCommand("basketball", "Shoot a basketball"),
    BotCommand("bowling", "Bowl a strike (maybe)"),
    BotCommand("football", "Kick a football"),
    BotCommand("slot", "Spin the slot machine"),
    BotCommand("oracle", "Ask the oracle a question"),
    BotCommand("tarot", "Draw a tarot card"),
    BotCommand("aura", "Read someone's aura"),
    BotCommand("emojiaura", "Emoji-only energy reading"),
    BotCommand("fate", "Today's cryptic fate"),
    BotCommand("whisper", "Secretly DM someone"),
    BotCommand("lore", "Random group lore drop"),
    BotCommand("starsign", "Zodiac reading"),
    BotCommand("confess", "Anonymous confession"),
    BotCommand("bestie", "Declare a bestie"),
    BotCommand("duo", "Generate a duo name"),
    BotCommand("friendship", "Compatibility score"),
    BotCommand("tagbestie", "Ping your declared bestie"),
    BotCommand("squad", "Most active friend group"),
    BotCommand("loyalty", "Loyalty score reading"),
    BotCommand("ship", "Ship two people together"),
    BotCommand("roast", "Playful roast"),
    BotCommand("compliment", "Nice compliment"),
    BotCommand("8ball", "Magic 8-ball answer"),
    BotCommand("vibe", "Vibe check the chat"),
    BotCommand("quote", "Random quote"),
    BotCommand("crush", "Privately pick a crush (reply to their message)"),
    BotCommand("clearcrush", "Clear your current pick"),
    BotCommand("randomship", "Bot randomly ships two active members"),
    BotCommand("secretadmirer", "Bot sends a random member an anonymous kind DM"),
    BotCommand("id", "Get user/chat ID"),
    BotCommand("info", "User info card"),
    BotCommand("remind", "Set a reminder"),
    BotCommand("mute", "Mute a user (admin)"),
    BotCommand("unmute", "Unmute a user (admin)"),
    BotCommand("ban", "Ban a user (admin)"),
    BotCommand("kick", "Kick a user (admin)"),
    BotCommand("warn", "Warn a user (admin)"),
    BotCommand("rules", "Show group rules"),
    BotCommand("warnings", "Check a user's warning count"),
    BotCommand("clearwarns", "Clear a user's warnings (admin)"),
    BotCommand("pin", "Pin the replied message (admin)"),
    BotCommand("unpin", "Unpin current message (admin)"),
    BotCommand("purge", "Delete N messages (admin)"),
    BotCommand("setrules", "Set group rules (admin)"),
    BotCommand("lock", "Restrict media/messages (admin)"),
    BotCommand("unlock", "Restore normal permissions (admin)"),
    BotCommand("stats", "Group activity stats"),
    BotCommand("topactive", "Ranked most active members"),
    BotCommand("msgcount", "A member's tracked message count"),
    BotCommand("groupinfo", "Group info card"),
    BotCommand("afk", "Mark yourself away"),
    BotCommand("report", "Report a message to admins"),
    BotCommand("poll", "Create a poll: /poll Q | A | B"),
    BotCommand("rank", "Activity-based rank tier"),
    BotCommand("setwelcome", "Set custom welcome message (admin)"),
    BotCommand("setgoodbye", "Set custom goodbye message (admin)"),
    BotCommand("invite", "Get a fresh invite link (admin)"),
    BotCommand("joined", "Recent joins log"),
    BotCommand("left", "Recent leaves log"),
    BotCommand("hangman", "Start hangman"),
    BotCommand("tictactoe", "Challenge someone (reply)"),
    BotCommand("ttt", "Make a tic-tac-toe move 1-9"),
    BotCommand("wordchain", "Start a word chain"),
    BotCommand("trivia", "Trivia by category"),
    BotCommand("wordle", "Get today's wordle"),
    BotCommand("daily", "Claim daily coins"),
    BotCommand("balance", "Check coin balance"),
    BotCommand("rob", "Try robbing someone (reply)"),
    BotCommand("gamble", "Gamble your coins"),
    BotCommand("richest", "Coin leaderboard"),
    BotCommand("moodboard", "Today's aesthetic mood"),
    BotCommand("dream", "AI-style dream interpretation"),
    BotCommand("manifest", "Stylized affirmation card"),
    BotCommand("matchmaker", "Bot pairs two random members"),
    BotCommand("friendshiptest", "Mini friendship quiz score"),
    BotCommand("hug", "Hug someone (reply)"),
    BotCommand("pat", "Pat someone (reply)"),
    BotCommand("highfive", "High-five someone (reply)"),
    BotCommand("impostor", "Start an impostor round"),
    BotCommand("revealimpostor", "Reveal who the impostor was"),
    BotCommand("ratethis", "Rate the replied message"),
    BotCommand("timecapsule", "Lock a message for later"),
    BotCommand("capsules", "List pending time capsules"),
]


async def _post_init(app: Application):
    """Runs once on startup — registers the / command menu with Telegram,
    and restores persisted data (coins, pending time capsules) from
    Redis if it's configured."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Command menu registered with Telegram.")

    await economy.load_from_storage()
    logger.info("Economy balances loaded from persistent storage.")

    await timecapsule.load_and_reschedule(app)
    logger.info("Time capsules loaded and rescheduled from persistent storage.")

    await chat.load_from_storage()
    logger.info("Chat mode settings loaded from persistent storage — /chat toggle now survives restarts.")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not found. Add it in Render's Environment tab.")
    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL not found. This is auto-set by Render on web "
            "services — if running locally instead, webhooks won't work; use "
            "polling for local testing."
        )

    app = Application.builder().token(TOKEN).post_init(_post_init).build()

    # ---- Start / Welcome ----
    app.add_handler(CommandHandler("start", utility.start_welcome))
    app.add_handler(CommandHandler("help", utility.help_command))

    # ---- Human-style chat ----
    app.add_handler(CommandHandler("chat", chat.toggle_chat))
    app.add_handler(CommandHandler("persona", chat.set_persona))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat.auto_reply), group=0)
    # Separate group so activity tracking runs on every message independently
    # of whether chat mode replied to it.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, friendship.track_message), group=1)
    app.add_handler(CommandHandler("sticker", chat.send_random_sticker))
    app.add_handler(CommandHandler("getstickerid", chat.get_sticker_id))
    app.add_handler(CommandHandler("gif", chat.send_random_gif))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, chat.maybe_react_to_message), group=3)
    app.add_handler(MessageHandler(filters.Sticker.ALL, chat.sticker_reply), group=4)
    app.add_handler(MessageHandler(filters.ANIMATION, chat.gif_reply), group=5)

    # ---- Games ----
    app.add_handler(CommandHandler("quiz", games.quiz))
    app.add_handler(CommandHandler("truth", games.truth))
    app.add_handler(CommandHandler("dare", games.dare))
    app.add_handler(CommandHandler("wyr", games.would_you_rather))
    app.add_handler(CommandHandler("nhie", games.never_have_i_ever))
    app.add_handler(CommandHandler("rps", games.rock_paper_scissors))
    app.add_handler(CommandHandler("riddle", games.riddle))
    app.add_handler(CommandHandler("riddleanswer", games.riddle_answer))
    app.add_handler(CommandHandler("scramble", games.scramble))
    app.add_handler(CommandHandler("unscramble", games.unscramble))
    app.add_handler(CommandHandler("guess", games.guess_number))
    app.add_handler(CommandHandler("leaderboard", games.leaderboard_cmd))
    app.add_handler(CommandHandler("dice", games.dice_game))
    app.add_handler(CommandHandler("darts", games.darts_game))
    app.add_handler(CommandHandler("basketball", games.basketball_game))
    app.add_handler(CommandHandler("bowling", games.bowling_game))
    app.add_handler(CommandHandler("football", games.football_game))
    app.add_handler(CommandHandler("slot", games.slot_game))
    app.add_handler(CommandHandler("hangman", games.hangman))
    app.add_handler(CommandHandler("hangmanguess", games.hangman_guess))
    app.add_handler(CommandHandler("tictactoe", games.tictactoe))
    app.add_handler(CommandHandler("ttt", games.ttt_move))
    app.add_handler(CommandHandler("wordchain", games.wordchain_start))
    app.add_handler(CommandHandler("chainword", games.chain_word))
    app.add_handler(CommandHandler("trivia", games.trivia_category))
    app.add_handler(CommandHandler("wordle", games.wordle))
    app.add_handler(CommandHandler("wordleguess", games.wordle_guess))

    # ---- Moderation ----
    app.add_handler(CommandHandler("mute", moderation.mute))
    app.add_handler(CommandHandler("unmute", moderation.unmute))
    app.add_handler(CommandHandler("ban", moderation.ban))
    app.add_handler(CommandHandler("kick", moderation.kick))
    app.add_handler(CommandHandler("warn", moderation.warn))
    app.add_handler(CommandHandler("rules", moderation.show_rules))
    app.add_handler(CommandHandler("warnings", moderation.check_warnings))
    app.add_handler(CommandHandler("clearwarns", moderation.clear_warnings))
    app.add_handler(CommandHandler("pin", moderation.pin))
    app.add_handler(CommandHandler("unpin", moderation.unpin))
    app.add_handler(CommandHandler("purge", moderation.purge))
    app.add_handler(CommandHandler("setrules", moderation.set_rules))
    app.add_handler(CommandHandler("lock", moderation.lock))
    app.add_handler(CommandHandler("unlock", moderation.unlock))

    # ---- Stats / Activity Log ----
    app.add_handler(CommandHandler("stats", stats.stats))
    app.add_handler(CommandHandler("topactive", stats.top_active))
    app.add_handler(CommandHandler("msgcount", stats.msg_count))

    # ---- Economy ----
    app.add_handler(CommandHandler("daily", economy.daily))
    app.add_handler(CommandHandler("balance", economy.balance))
    app.add_handler(CommandHandler("rob", economy.rob))
    app.add_handler(CommandHandler("gamble", economy.gamble))
    app.add_handler(CommandHandler("richest", economy.economy_leaderboard))

    # ---- Utility ----
    app.add_handler(CommandHandler("id", utility.get_id))
    app.add_handler(CommandHandler("info", utility.user_info))
    app.add_handler(CommandHandler("remind", utility.remind))
    app.add_handler(CommandHandler("groupinfo", utility.group_info))
    app.add_handler(CommandHandler("afk", utility.set_afk))
    app.add_handler(CommandHandler("report", utility.report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, utility.check_afk_mentions), group=2)

    # ---- Aesthetic / Mysterious ----
    app.add_handler(CommandHandler("oracle", aesthetic.oracle))
    app.add_handler(CommandHandler("tarot", aesthetic.tarot))
    app.add_handler(CommandHandler("aura", aesthetic.aura))
    app.add_handler(CommandHandler("emojiaura", aesthetic.emoji_aura))
    app.add_handler(CommandHandler("fate", aesthetic.fate))
    app.add_handler(CommandHandler("whisper", aesthetic.whisper))
    app.add_handler(CommandHandler("lore", aesthetic.lore))
    app.add_handler(CommandHandler("starsign", aesthetic.starsign))
    app.add_handler(CommandHandler("confess", aesthetic.confess))
    app.add_handler(CommandHandler("moodboard", aesthetic.moodboard))
    app.add_handler(CommandHandler("dream", aesthetic.dream))
    app.add_handler(CommandHandler("manifest", aesthetic.manifest))

    # ---- Friendship ----
    app.add_handler(CommandHandler("bestie", friendship.bestie))
    app.add_handler(CommandHandler("duo", friendship.duo))
    app.add_handler(CommandHandler("friendship", friendship.friendship_score))
    app.add_handler(CommandHandler("tagbestie", friendship.tag_bestie))
    app.add_handler(CommandHandler("squad", friendship.squad))
    app.add_handler(CommandHandler("loyalty", friendship.loyalty))
    app.add_handler(CommandHandler("ship", friendship.ship))
    app.add_handler(CommandHandler("randomship", friendship.random_ship))
    app.add_handler(CommandHandler("matchmaker", friendship.matchmaker))
    app.add_handler(CommandHandler("friendshiptest", friendship.friendship_test))
    app.add_handler(CommandHandler("hug", friendship.hug))
    app.add_handler(CommandHandler("pat", friendship.pat))
    app.add_handler(CommandHandler("highfive", friendship.highfive))
    app.add_handler(CommandHandler("slap", friendship.slap))
    app.add_handler(CommandHandler("kiss", friendship.kiss))
    app.add_handler(CommandHandler("poke", friendship.poke))
    app.add_handler(CommandHandler("cuddle", friendship.cuddle))
    app.add_handler(CommandHandler("wave", friendship.wave))
    app.add_handler(CommandHandler("bite", friendship.bite))
    app.add_handler(CommandHandler("tickle", friendship.tickle))

    # ---- Fun / Social ----
    app.add_handler(CommandHandler("roast", fun.roast))
    app.add_handler(CommandHandler("compliment", fun.compliment))
    app.add_handler(CommandHandler("8ball", fun.eight_ball))
    app.add_handler(CommandHandler("vibe", fun.vibe))
    app.add_handler(CommandHandler("quote", fun.quote))
    app.add_handler(CommandHandler("poll", fun.poll))
    app.add_handler(CommandHandler("rank", fun.rank))
    app.add_handler(CommandHandler("ratethis", fun.rate_this))
    app.add_handler(CommandHandler("impostor", fun.impostor_start))
    app.add_handler(CommandHandler("revealimpostor", fun.impostor_reveal))

    # ---- Matchmaking ----
    app.add_handler(CommandHandler("crush", matchmaking.set_crush))
    app.add_handler(CommandHandler("clearcrush", matchmaking.clear_crush))
    app.add_handler(CommandHandler("secretadmirer", matchmaking.secret_admirer))

    # ---- Events (join/leave/welcome/goodbye) ----
    app.add_handler(CommandHandler("setwelcome", events.set_welcome))
    app.add_handler(CommandHandler("setgoodbye", events.set_goodbye))
    app.add_handler(CommandHandler("invite", events.get_invite))
    app.add_handler(CommandHandler("joined", events.show_joined))
    app.add_handler(CommandHandler("left", events.show_left))
    app.add_handler(ChatMemberHandler(events.on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # ---- Time Capsule ----
    app.add_handler(CommandHandler("timecapsule", timecapsule.timecapsule))
    app.add_handler(CommandHandler("capsules", timecapsule.list_capsules))

    # Use the token as the URL path — keeps the webhook endpoint private,
    # since guessing it means guessing your token.
    webhook_path = TOKEN
    full_webhook_url = f"{RENDER_EXTERNAL_URL}/{webhook_path}"

    logger.info(f"Starting webhook at {full_webhook_url}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=full_webhook_url,
    )


if __name__ == "__main__":
    main()
