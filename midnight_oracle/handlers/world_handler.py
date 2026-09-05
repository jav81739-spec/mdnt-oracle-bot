"""Telegram commands, poll lifecycle, and word-game routing."""
from __future__ import annotations
import asyncio,json
from datetime import datetime,timezone,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..games.game_engine import GameEngine
from ..games.truth_dare import TruthDareGame
from ..games.would_you_rather import WouldYouRatherGame
from ..games.never_have_i_ever import NeverHaveIEverGame
from ..games.word_scramble import WordScrambleGame
from ..games.prediction import PredictionEngine
from core.storage import storage

def _member(update:Update)->object:
    """Build the member object consumed by game engines."""
    u=update.effective_user;c=update.effective_chat;return type('Member',(),{'user_id':u.id,'group_id':c.id,'preferred_name':u.first_name or 'friend','relationship_tier':'regular'})()

async def start_game(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Start the requested game, using the native WYR poll lifecycle."""
    if not update.effective_chat or update.effective_chat.type not in {'group','supergroup'}:return
    db=context.application.bot_data['oracle_db'];name=update.message.text.split()[0].lstrip('/').split('@')[0].casefold();member=_member(update)
    if name=='wyr':
        try:
            poll=await WouldYouRatherGame(db).start_poll(update.effective_chat.id,context.bot,member.user_id);sched=context.application.bot_data.get('oracle_scheduler')
            if sched:
                row=await db.get_active_wyr_session(update.effective_chat.id);state=json.loads(row['state']);run_at=datetime.fromtimestamp(float(state['started_at'])+60,tz=timezone.utc).astimezone(sched.timezone);sched.scheduler.add_job(WouldYouRatherGame(db).close_poll,'date',run_date=run_at,args=[poll.poll.id,context.bot,update.effective_chat.id],id=f'wyr_close_{poll.poll.id}',replace_existing=True)
        except Exception:await update.effective_message.reply_text('☾ Could not open that poll right now.')
        return
    cls={'tod':TruthDareGame,'nhie':NeverHaveIEverGame,'scramble':WordScrambleGame}.get(name)
    if not cls:return
    if name=='scramble':
        async with storage.lock(f'scramble:{update.effective_chat.id}') as acquired:
            if not acquired:
                await update.effective_message.reply_text('⏳ The game engine is busy — try again.')
                return
            text=await cls(db).start(update.effective_chat.id,member)
    else:
        text=await cls(db).start(update.effective_chat.id,member)
    await update.effective_message.reply_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('End game',callback_data='game:end')]]))
    if name=='scramble' and text and 'already running' not in text:_schedule_scramble(context,update.effective_chat.id)

def _schedule_scramble(context:ContextTypes.DEFAULT_TYPE,group_id:int)->None:
    """Schedule the active scramble's 30-second timeout."""
    sched=context.application.bot_data.get('oracle_scheduler');db=context.application.bot_data.get('oracle_db')
    if sched and db:
        row_state=None
        # Scheduling is best-effort; durable round_start_time is the source of truth.
        # The timeout handler re-checks state before mutating anything.
        sched.scheduler.add_job(_scramble_timeout,'date',run_date=datetime.now(sched.timezone)+timedelta(seconds=30),args=[context.application,db,group_id],id=f'scramble_timeout_{group_id}',replace_existing=True)

async def _scramble_timeout(application,db,group_id:int)->None:
    """Resolve an unanswered scramble round and continue or finish."""
    async with storage.lock(f'scramble:{group_id}') as acquired:
        if not acquired:return
        row=await WordScrambleGame(db).get_active(group_id)
        if not row:return
        state=json.loads(row['state'])
        started=float(state.get('round_start_time',0) or 0)
        if not state.get('awaiting_answer') or (started and datetime.now(timezone.utc).timestamp()-started<29):return
        text=await WordScrambleGame(db).timeout(group_id)
        if not text:return
        await application.bot.send_message(group_id,text)
        row=await WordScrambleGame(db).get_active(group_id)
        if row and json.loads(row['state']).get('awaiting_answer'):
            sched=application.bot_data.get('oracle_scheduler')
            if sched:sched.scheduler.add_job(_scramble_timeout,'date',run_date=datetime.now(sched.timezone)+timedelta(seconds=30),args=[application,db,group_id],id=f'scramble_timeout_{group_id}',replace_existing=True)

async def handle_game_message(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Accept only correct answers for active scramble sessions."""
    msg=update.effective_message;chat=update.effective_chat;user=update.effective_user
    if not msg or not chat or not user or not msg.text or chat.type not in {'group','supergroup'}:return
    game=WordScrambleGame(context.application.bot_data['oracle_db']);row=await game.get_active(chat.id)
    if not row:return
    state=json.loads(row['state'])
    if not state.get('awaiting_answer'):return
    ok,text,finished=await game.submit_answer(chat.id,user.id,user.first_name or 'friend',msg.text)
    if not ok:return
    sched=context.application.bot_data.get('oracle_scheduler')
    if sched:
        try:sched.scheduler.remove_job(f'scramble_timeout_{chat.id}')
        except Exception:pass
    await msg.reply_text(text or '☾ Counted.')
    if finished:
        async with storage.lock(f'scramble:{chat.id}') as acquired:
            if acquired:
                final=await game.finish(chat.id)
                if final:await msg.reply_text(final)
    else:
        await asyncio.sleep(3)
        async with storage.lock(f'scramble:{chat.id}') as acquired:
            if not acquired:return
            next_text=await game.next_round(chat.id)
            if next_text:await msg.reply_text(next_text);_schedule_scramble(context,chat.id)

async def handle_poll_answer(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Silently store a WYR poll answer."""
    p=update.poll_answer
    if p and p.option_ids:await WouldYouRatherGame(context.application.bot_data['oracle_db']).handle_poll_answer(p.poll_id,p.user.id,p.option_ids[0])

async def handle_poll(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Close an active WYR session if Telegram reports the poll closed early."""
    p=update.poll
    if not p or not p.is_closed:return
    db=context.application.bot_data.get('oracle_db');sched=context.application.bot_data.get('oracle_scheduler')
    if not db:return
    for r in await db.fetchall("SELECT state FROM game_sessions WHERE game_type='would_you_rather' AND is_active=1"):
        state=json.loads(r['state'])
        if str(state.get('poll_id'))==str(p.id):
            if sched:
                try:sched.scheduler.remove_job(f'wyr_close_{p.id}')
                except Exception:pass
            await WouldYouRatherGame(db).close_poll(p.id,context.bot,int(state['group_id']));return

async def end_game(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Gracefully end an active game, including scramble partial scores."""
    if not update.effective_chat:return
    db=context.application.bot_data['oracle_db'];gid=update.effective_chat.id;sched=context.application.bot_data.get('oracle_scheduler')
    if sched:
        try:sched.scheduler.remove_job(f'scramble_timeout_{gid}')
        except Exception:pass
    row=await db.fetchone("SELECT game_type FROM game_sessions WHERE group_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",(gid,))
    if row and row['game_type']=='word_scramble':
        async with storage.lock(f'scramble:{gid}') as acquired:
            if not acquired:return
            await update.effective_message.reply_text(await WordScrambleGame(db).endgame(gid));return
    await update.effective_message.reply_text(await GameEngine(db).endgame(gid))

async def game_callback(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Handle game buttons and acknowledge Telegram callbacks."""
    q=update.callback_query
    if not q:return
    await q.answer();db=context.application.bot_data['oracle_db']
    if q.data=='game:end':await q.edit_message_text(await GameEngine(db).endgame(q.message.chat_id))
