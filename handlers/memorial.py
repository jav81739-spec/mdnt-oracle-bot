"""☾ The Quiet Graveyard — a remembrance space for every fallen soul."""
from __future__ import annotations
from telegram.ext import Application, CommandHandler, ContextTypes

_TEXT = (
    "☾ *THE QUIET GRAVEYARD*\n"
    "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
    "For every soul lost beneath the midnight sky.\n\n"
    "No banners.\nNo victories.\nNo enemies.\n\n"
    "Only a quiet place to rest.\n"
    "Even those who once stood on the other side.\n\n"
    "_A soul does not become less worthy of peace\n"
    "because it once stood against us._\n\n"
    "🕊️ *May every fallen soul rest in peace.*\n\n"
    "🌙 *— Midnight Oracle*"
)

async def graveyard(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(_TEXT, parse_mode="Markdown")

def register(app: Application) -> None:
    existing = {
        str(c).lower().lstrip("/")
        for hs in getattr(app, "handlers", {}).values()
        for h in hs
        for c in (getattr(h, "commands", None) or ())
    }
    if "graveyard" not in existing:
        app.add_handler(CommandHandler("graveyard", graveyard), group=0)
