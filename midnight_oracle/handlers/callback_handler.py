"""Inline keyboard callbacks including secret-event reveal lifecycle."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes

async def handle_callback(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Handle social callbacks and atomically reveal secret events."""
    query=update.callback_query
    if not query:return
    try:
        data=query.data or ''
        if data.startswith('secret:'):
            try:event_id=int(data.split(':',1)[1])
            except ValueError:await query.answer('☾ Invalid reveal.',show_alert=False);return
            db=context.application.bot_data['oracle_db'];engine=context.application.bot_data.get('secret_event_engine')
            if engine is None:
                from ..engines.secret_event_engine import SecretEventEngine
                engine=SecretEventEngine(db);context.application.bot_data['secret_event_engine']=engine
            if await db.is_revealed(event_id):await query.answer('☾ Already revealed.',show_alert=False);return
            ok=await engine.reveal(event_id,context.bot,query.message.message_id if query.message else None,query.from_user.id,query.message.chat_id if query.message else None)
            await query.answer('' if ok else '☾ Already revealed.',show_alert=False);return
        await query.answer()
        value=data.split(':',1)
        if value[0]=='mood':await query.edit_message_text(f"☾ noted — {value[1] if len(value)>1 else 'mood'}")
        elif value[0]=='truth':await query.answer('Passed. No explanation needed.' if len(value)>1 and value[1]=='pass' else 'Take your time.',show_alert=False)
    except Exception:return
