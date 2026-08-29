"""Telegram commands for Midnight Oracle, extended with Phase 3-4 surfaces."""
from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from ..generators.truth_generator import question
from ..memory_engine import MemoryEngine
from ..config import WEBAPP_URL

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Welcome a user without exposing implementation details."""; await update.effective_message.reply_text("☾ Midnight Oracle\n\nSomeone in the room who remembers you.")
async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show the compact public command guide."""; await update.effective_message.reply_text("☾ /oracle · /truth · /memory · /mymemory · /forget\n/tod · /wyr · /nhie · /scramble\n/predict · /predictions · /house · /quiet · /wake")
async def oracle(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Provide a direct summon response."""; await update.effective_message.reply_text("☾ I'm here. What's on your mind?")
async def truth(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Send a truth question with answer/pass controls."""; text=question(context.args[0] if context.args else 'light'); await update.effective_message.reply_text(f"☾ {text}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Answer',callback_data='truth:answer'),InlineKeyboardButton('Pass',callback_data='truth:pass')]]))
async def memory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show aggregate group memory counts without exposing private member details."""; db=context.application.bot_data.get('oracle_db');
    
    if not db:return
    rows=await db.fetchall("SELECT memory_type,COUNT(*) FROM member_memory WHERE group_id=? AND is_active=1 GROUP BY memory_type",(update.effective_chat.id,)); await update.effective_message.reply_text('☾ Group memory: '+(', '.join(f'{r[0]} {r[1]}' for r in rows) or 'quiet for now')+'.')
async def mymemory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show bounded memory in DM, never as a public dump."""; db=context.application.bot_data.get('oracle_db'); u=update.effective_user
    if not db or not u:return
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,)); gid=int(row[0]) if row else 0
    if not gid:await update.effective_message.reply_text("☾ We haven't built a memory together yet.");return
    profile=await MemoryEngine(db).get(u.id,gid); items=list(profile.interests[:2])+list(profile.wins[:2])+list(profile.themes[:2]); await update.effective_message.reply_text('☾ What I remember\n'+('\n'.join('• '+x for x in items) if items else 'Nothing heavy stored. Just the moments that mattered.'))
async def forget(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Deactivate matching memory for the requesting member."""; db=context.application.bot_data.get('oracle_db'); u=update.effective_user
    if not db or not u or not context.args:await update.effective_message.reply_text('Tell me what to forget: /forget <topic>');return
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,));gid=int(row[0]) if row else 0
    n=await db.delete_memories_matching(u.id,gid,' '.join(context.args)) if gid else 0;await update.effective_message.reply_text('☾ Forgotten.' if n else "☾ I couldn't find that memory.")
async def quiet(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Silence ambient replies for two hours for an administrator."""; 
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}: await context.application.bot_data['oracle_db'].set_cooldown('group',str(update.effective_chat.id),'ambient',__import__('time').time()+7200); await update.effective_message.reply_text('☾ Quiet mode. I will stay out for two hours.')
async def wake(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Wake ambient replies for an administrator."""; 
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}: await context.application.bot_data['oracle_db'].execute("DELETE FROM cooldowns WHERE scope='group' AND scope_id=? AND cooldown_type='ambient'",(str(update.effective_chat.id),)); await update.effective_message.reply_text("☾ I'm awake.")
async def house(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Open the configured Telegram Mini App when one is deployed.""";
    if not WEBAPP_URL: await update.effective_message.reply_text('☾ House is being prepared.'); return
    await update.effective_message.reply_text('☾ Oracle House',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Enter House',web_app=WebAppInfo(WEBAPP_URL))]]))
