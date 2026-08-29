"""Inline keyboard callbacks including secret-event reveal lifecycle."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Midnight Oracle callbacks without leaking internal state."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    try:
        if data.startswith(("reveal_", "secret:")):
            raw = data.split("_", 1)[1] if data.startswith("reveal_") else data.split(":", 1)[1]
            event_id = int(raw)
            db = context.application.bot_data.get("oracle_db")
            if db is None:
                await query.answer("", show_alert=False)
                return

            from ..engines.secret_event_engine import SecretEventEngine

            engine = context.application.bot_data.get("secret_event_engine") or SecretEventEngine(db)
            context.application.bot_data["secret_event_engine"] = engine

            if await db.is_revealed(event_id):
                await query.answer("☾ Already revealed.", show_alert=False)
                return

            message = query.message
            ok = await engine.reveal(
                event_id,
                context.bot,
                message.message_id if message else None,
                query.from_user.id,
                message.chat_id if message else None,
            )
            if ok:
                scheduler = context.application.bot_data.get("oracle_scheduler")
                if scheduler:
                    try:
                        scheduler.scheduler.remove_job(f"auto_reveal_{event_id}")
                    except Exception:
                        pass
                await query.answer("", show_alert=False)
            else:
                await query.answer("☾ Already revealed.", show_alert=False)
            return

        if data == "game:end" and query.message:
            db = context.application.bot_data.get("oracle_db")
            if db is None:
                await query.answer("", show_alert=False)
                return
            from ..games.word_scramble import WordScrambleGame

            row = await db.fetchone(
                "SELECT game_type FROM game_sessions WHERE group_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",
                (query.message.chat_id,),
            )
            if row and row["game_type"] == "word_scramble":
                await query.answer("", show_alert=False)
                await query.edit_message_text(await WordScrambleGame(db).endgame(query.message.chat_id))
                return

        await query.answer("", show_alert=False)
    except Exception:
        try:
            await query.answer("", show_alert=False)
        except Exception:
            pass
