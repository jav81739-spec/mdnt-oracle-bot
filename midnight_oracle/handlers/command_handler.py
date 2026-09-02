"""Telegram commands for Midnight Oracle, preserving the original public surface."""
from __future__ import annotations
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from ..generators.truth_generator import question
from ..memory_engine import MemoryEngine

def _house_url() -> str:return (os.getenv("ORACLE_WEBAPP_URL") or os.getenv("ORACLE_MINI_APP_URL") or os.getenv("MINI_APP_URL") or "").strip()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    user=update.effective_user; name=f"@{user.username}" if user and user.username else (user.first_name if user else "you")
    if update.effective_chat and update.effective_chat.type=="private":text=f"🌙 *Midnight Oracle*\n\nHey, {name}.\n\nI'm around for conversation, games, strange little moments and whatever the room turns into.\n\nTry /help when you want the map."
    else:text=f"🌙 *Midnight Oracle*\n\nHey, {name}. I'm in.\n\nI'll join the room when there's actually something worth adding."
    await update.effective_message.reply_text(text,parse_mode="Markdown")

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    text="""🌙 *MIDNIGHT ORACLE*
━━━━━━━━━━━━━━━━━━
_conversation, games, readings, chaos and the occasional unexpected moment._

━━━━ *🔮 READINGS* ━━━━
`/oracle` `/aura` `/vibecheck` `/identity` `/shadow` `/element` `/corecode`
`/universe` `/ritual` `/duality` `/nightreport` `/sigil` `/glitch`

━━━━ *💬 CONVERSATION* ━━━━
`/chat` `/persona` `/vent` `/checkin` `/streakcheck`

━━━━ *🎮 GAMES* ━━━━
`/quiz` `/truth` `/dare` `/wyr` `/nhie` `/rps`
`/riddle` `/riddleanswer` `/scramble` `/unscramble` `/guess` `/leaderboard`
`/dice` `/darts` `/basketball` `/bowling` `/football` `/slot`
`/hangman` `/hangmanguess` `/tictactoe` `/ttt` `/wordchain` `/chainword`
`/trivia` `/wordle` `/wordleguess` `/ratethis` `/impostor` `/revealimpostor`

━━━━ *👥 PEOPLE* ━━━━
`/bestie` `/duo` `/friendship` `/ship` `/tagbestie` `/squad` `/loyalty`
`/hug` `/pat` `/highfive` `/slap` `/kiss` `/poke` `/cuddle` `/wave` `/bite` `/tickle`

━━━━ *💘 MATCHMAKING* ━━━━
`/matchmaker` `/randomship` `/secretadmirer` `/crush` `/clearcrush`

━━━━ *🎉 FUN* ━━━━
`/roast` `/compliment` `/8ball` `/vibe` `/quote` `/poll` `/rank`

━━━━ *🛠️ UTILITY* ━━━━
`/id` `/info` `/remind` `/groupinfo` `/afk` `/report`

━━━━ *📊 STATS* ━━━━
`/stats` `/topactive` `/msgcount` `/joined` `/left`

━━━━ *💰 ECONOMY* ━━━━
`/daily` `/balance` `/rob` `/gamble` `/richest`

━━━━ *💍 MARRIAGE & SHOP* ━━━━
`/marry` `/accept` `/divorce` `/profile` `/work` `/chests`
`/shop` `/buy` `/inventory` `/gift` `/settings`

━━━━ *⏳ TIME CAPSULE* ━━━━
`/timecapsule` `/capsules`

━━━━ *💀 DEATH GAMES* ━━━━
`/survive` `/revive` `/deathstatus` `/roulette` `/deathgame` `/joingame`
`/startround` `/vote` `/endgame`

━━━━ *☾ CORE* ━━━━
`/memory` `/mymemory` `/forget` `/quiet` `/wake` `/tod` `/predict` `/predictions` `/house`

━━━━━━━━━━━━━━━━━━
_private and owner controls stay private._"""
    await update.effective_message.reply_text(text,parse_mode="Markdown")

async def oracle(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:await update.effective_message.reply_text("☾ I'm here. What's on your mind?")
async def truth(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    text=question(context.args[0] if context.args else 'light');await update.effective_message.reply_text(f"☾ {text}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Answer',callback_data='truth:answer'),InlineKeyboardButton('Pass',callback_data='truth:pass')]]))
async def memory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    await update.effective_message.reply_text("☾ I keep the room's moments quietly — not a public ledger. Ask /mymemory for what belongs to you.")
async def mymemory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    db=context.application.bot_data.get('oracle_db');u=update.effective_user
    if not db or not u:return
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,));gid=int(row[0]) if row else 0
    if not gid:return await update.effective_message.reply_text("☾ We haven't built a memory together yet.")
    profile=await MemoryEngine(db).get(u.id,gid);items=list(profile.interests[:2])+list(profile.wins[:2])+list(profile.themes[:2]);await update.effective_message.reply_text('☾ What I remember\n'+('\n'.join('• '+x for x in items) if items else 'Nothing heavy stored. Just the moments that mattered.'))
async def forget(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    db=context.application.bot_data.get('oracle_db');u=update.effective_user
    if not db or not u or not context.args:return await update.effective_message.reply_text('Tell me what to forget: /forget <topic>')
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,));gid=int(row[0]) if row else 0
    n=await db.delete_memories_matching(u.id,gid,' '.join(context.args)) if gid else 0;await update.effective_message.reply_text('☾ Forgotten.' if n else "☾ I couldn't find that memory.")
async def quiet(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}:await context.application.bot_data['oracle_db'].set_cooldown('group',str(update.effective_chat.id),'ambient',__import__('time').time()+7200);await update.effective_message.reply_text('☾ Quiet mode. I will stay out for two hours.')
async def wake(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}:await context.application.bot_data['oracle_db'].execute("DELETE FROM cooldowns WHERE scope='group' AND scope_id=? AND cooldown_type='ambient'",(str(update.effective_chat.id),));await update.effective_message.reply_text("☾ I'm awake.")
async def house(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    url=_house_url()
    if not url:return await update.effective_message.reply_text('☾ Oracle House is quiet for now.')
    await update.effective_message.reply_text('☾ *Oracle House*\n\nA quieter room for memories, achievements, group pulse and games.',parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Enter the House 🌙',web_app=WebAppInfo(url=url))]]))
