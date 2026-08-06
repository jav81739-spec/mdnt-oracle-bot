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
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from handlers import chat, games, moderation, utility, aesthetic, friendship

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


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN not found. Add it in Render's Environment tab.")
    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL not found. This is auto-set by Render on web "
            "services — if running locally instead, webhooks won't work; use "
            "polling for local testing."
        )

    app = Application.builder().token(TOKEN).build()

    # ---- Start / Welcome ----
    app.add_handler(CommandHandler("start", utility.start_welcome))
    app.add_handler(CommandHandler("help", utility.help_command))

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
