"""Telegram commands and callbacks for Phase 3 games."""
from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..games.game_engine import GameEngine
from ..games.truth_dare import TruthDareGame
from ..games.would_you_rather import WouldYouRatherGame
from ..games.never_have_i_ever import NeverHaveIEverGame
from ..games.word_scramble import WordScrambleGame
from ..games.prediction import PredictionEngine

def _member(update:Update)->object:
    """Build the small member object consumed by game engines."""
    u=update.effective_user; c=update.effective_chat
    return type('Member',(),{'user_id':u.id,'group_id':c.id,'preferred_name':u.first_name or 'friend','relationship_tier':'regular'})()

async def start_game(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Start the game requested by the command name."""
    if not update.effective_chat or update.effective_chat.type not in {'group','supergroup'}: return
    db=context.application.bot_data['oracle_db']; name=update.message.text.split()[0].lstrip('/').split('@')[0].casefold(); cls={'tod':TruthDareGame,'wyr':WouldYouRatherGame,'nhie':NeverHaveIEverGame,'scramble':WordScrambleGame}.get(name)
    if not cls:return
    text=await cls(db).start(update.effective_chat.id,_member(update)); await update.effective_message.reply_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('End game',callback_data='game:end')]]))

async def end_game(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Gracefully end the active game."""
    if update.effective_chat: await update.effective_message.reply_text(await GameEngine(context.application.bot_data['oracle_db']).endgame(update.effective_chat.id))

async def game_callback(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Handle safe game buttons and acknowledge Telegram callbacks."""
    q=update.callback_query
    if not q:return
    await q.answer(); db=context.application.bot_data['oracle_db']; chat=q.message.chat_id
    if q.data=='game:end': await q.edit_message_text(await GameEngine(db).endgame(chat))
