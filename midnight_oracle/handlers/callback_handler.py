"""Inline keyboard callbacks including secret-event reveal lifecycle."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle social callbacks and atomically reveal secret events."""
    query = update.callback_query
    if not query:
        return
    try:
        data = query.data or ''
        if data.startswith('reveal_') or data.startswith('secret:'):
            raw = data.split('_', 1)[1] if data.startswith('reveal_') else data.split(':', 1)[1]
            event_id = int(raw)
            db = context.application.bot_data['oracle_db']
            from ..engines.secret_event_engine import SecretEventEngine
            engine = context.application.bot_data.get('secret_event_engine') or SecretEventEngine(db)
            context.application.bot_data['secret_event_engine'] = engine
            if await db.is_revealed(event_id):
                await query.answer('☾ Already revealed.', show_alert=False)
                return
            message = query.message
            ok = await engine.reveal(event_id, context.bot, message.message_id if message else None, query.from_user.id, message.chat_id if message else None)
            if ok:
                scheduler = context.application.bot_data.get('oracle_scheduler')
                if scheduler:
                    try:
                        scheduler.scheduler.remove_job(f'auto_reveal_{event_id}')
                    except Exception:
                        pass
                await query.answer('', show_alert=False)
            else:
                await query.answer('☾ Already revealed.', show_alert=False)
            return
        await query.answer()
        value = data.split(':', 1)
        if value[0] == 'mood':
            await query.edit_message_text(f"☾ noted — {value[1] if len(value)>1 else 'mood'}")
        elif value[0] == 'truth':
            await query.answer('Passed. No explanation needed.' if len(value)>1 and value[1]=='pass' else 'Take your time.', show_alert=False)
    except Exception:
        try:
            await query.answer('', show_alert=False)
        except Exception:
            pass
