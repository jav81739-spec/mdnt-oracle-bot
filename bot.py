"""
Main entry point for the bot.
Run with: python bot.py
Requires BOT_TOKEN set in .env (see .env.example)
"""
import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from handlers import chat, games, moderation, utility, aesthetic, friendship

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not found. Add it to your .env file.")

    app = Application.builder().token(TOKEN).build()

    # ---- Human-style chat ----
    app.add_handler(CommandHandler("chat", chat.toggle_chat))
    app.add_handler(CommandHandler("persona", chat.set_persona))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat.auto_reply))

    # ---- Games ----
    app.add_handler(CommandHandler("quiz", games.quiz))
    app.add_handler(CommandHandler("truth", games.truth))
    app.add_handler(CommandHandler("dare", games.dare))
    app.add_handler(CommandHandler("wyr", games.would_you_rather))
    app.add_handler(CommandHandler("rps", games.rock_paper_scissors))

    # ---- Moderation ----
    app.add_handler(CommandHandler("mute", moderation.mute))
    app.add_handler(CommandHandler("unmute", moderation.unmute))
    app.add_handler(CommandHandler("ban", moderation.ban))
    app.add_handler(CommandHandler("kick", moderation.kick))
    app.add_handler(CommandHandler("warn", moderation.warn))
    app.add_handler(CommandHandler("rules", moderation.show_rules))

    # ---- Utility ----
    app.add_handler(CommandHandler("id", utility.get_id))
    app.add_handler(CommandHandler("info", utility.user_info))
    app.add_handler(CommandHandler("remind", utility.remind))

    # ---- Aesthetic / Mysterious ----
    app.add_handler(CommandHandler("oracle", aesthetic.oracle))
    app.add_handler(CommandHandler("tarot", aesthetic.tarot))
    app.add_handler(CommandHandler("aura", aesthetic.aura))
    app.add_handler(CommandHandler("confess", aesthetic.confess))

    # ---- Friendship ----
    app.add_handler(CommandHandler("bestie", friendship.bestie))
    app.add_handler(CommandHandler("duo", friendship.duo))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
