"""Telegram handlers for public group predictions."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from telegram import Update
from telegram.ext import ContextTypes
from ..games.prediction import PredictionEngine

async def predict(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Create a prediction for seven days from now."""
    if not update.effective_chat or not update.effective_user or not context.args:return
    text=' '.join(context.args); await PredictionEngine(context.application.bot_data['oracle_db']).create(update.effective_chat.id,update.effective_user.id,text,(datetime.now(timezone.utc)+timedelta(days=7)).timestamp()); await update.effective_message.reply_text('☾ Prediction sealed for seven days from now.')
async def predictions(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """List pending public predictions without private member details."""
    if not update.effective_chat:return
    rows=await PredictionEngine(context.application.bot_data['oracle_db']).pending(update.effective_chat.id); text='\n'.join(f'• {r[2]}' for r in rows[:10]) or 'Nothing is waiting for its day.'; await update.effective_message.reply_text('☾ Pending predictions\n'+text)
