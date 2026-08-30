"""Telegram commands for Midnight Oracle, preserving the original public surface."""
from __future__ import annotations
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from ..generators.truth_generator import question
from ..memory_engine import MemoryEngine

def _house_url() -> str:
    """Return the configured Mini App URL using supported environment names."""
    return (os.getenv("ORACLE_WEBAPP_URL") or os.getenv("ORACLE_MINI_APP_URL") or os.getenv("MINI_APP_URL") or "").strip()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Welcome a user without exposing implementation details."""
    user=update.effective_user; name=f"@{user.username}" if user and user.username else (user.first_name if user else "you")
    if update.effective_chat and update.effective_chat.type=="private":
        text=f"🌙 *Midnight Oracle*\n┄┄┄┄┄┄┄┄┄┄┄┄\n\n_{name}._\n\n_the oracle has been here longer than you think._\n\n_add it to your group and watch what happens._\n\n_it watches. it names. it reveals._\n_all by itself. every day._\n\n_type /help to see everything it can do._\n\n✦ *— Midnight Oracle*"
    else:
        text="🌙 *Midnight Oracle has entered the group.*\n\n_it's watching now._\n\n_it will speak when it has something to say._\n_which will be soon._\n\n_type /help to see what the oracle does._\n\n👁️ *— Midnight Oracle*"
    await update.effective_message.reply_text(text,parse_mode="Markdown")

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show the complete public command guide while keeping private controls hidden."""
    text="""🌙 *MIDNIGHT ORACLE*
━━━━━━━━━━━━━━━━━━
_it watches. it names. it reveals._

━━━━ *🔮 ORACLE READINGS* ━━━━
`/oracle` `/aura` `/vibecheck` `/identity` `/shadow` `/element` `/corecode`
`/universe` `/ritual` `/duality` `/nightreport` `/sigil` `/glitch`

━━━━ *🌙 DAILY RITUALS* ━━━━
`/checkin` `/streakcheck`

━━━━ *💬 EXPRESSION* ━━━━
`/chat` `/persona` `/vent`

━━━━ *🎮 GAMES* ━━━━
`/quiz` `/truth` `/dare` `/wyr` `/nhie` `/rps`
`/riddle` `/riddleanswer` `/scramble` `/unscramble` `/guess` `/leaderboard`
`/dice` `/darts` `/basketball` `/bowling` `/football` `/slot`
`/hangman` `/hangmanguess` `/tictactoe` `/ttt` `/wordchain` `/chainword`
`/trivia` `/wordle` `/wordleguess` `/ratethis` `/impostor` `/revealimpostor`

━━━━ *👥 FRIENDSHIP* ━━━━
`/bestie` `/duo` `/friendship` `/ship` `/tagbestie` `/squad` `/loyalty` `/friendshiptest`
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

━━━━ *💀 DEATH LIFE GAMES* ━━━━
`/survive` `/revive` `/deathstatus` `/roulette` `/deathgame` `/joingame`
`/startround` `/vote` `/endgame`

━━━━ *☾ CORE* ━━━━
`/memory` `/mymemory` `/forget` `/quiet` `/wake` `/tod` `/predict` `/predictions` `/house`

━━━━━━━━━━━━━━━━━━
_private/owner-only controls are intentionally not listed here._
✦ *— Midnight Oracle*"""
    await update.effective_message.reply_text(text,parse_mode="Markdown")

async def oracle(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Provide a direct Oracle summon response."""
    await update.effective_message.reply_text("☾ I'm here. What's on your mind?")

async def truth(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Send a truth question with answer/pass controls."""
    text=question(context.args[0] if context.args else 'light'); await update.effective_message.reply_text(f"☾ {text}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Answer',callback_data='truth:answer'),InlineKeyboardButton('Pass',callback_data='truth:pass')]]))

async def memory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show aggregate group memory counts without exposing private member details."""
    db=context.application.bot_data.get('oracle_db')
    if not db:return
    rows=await db.fetchall("SELECT memory_type,COUNT(*) FROM member_memory WHERE group_id=? AND is_active=1 GROUP BY memory_type",(update.effective_chat.id,)); await update.effective_message.reply_text('☾ Group memory: '+(', '.join(f'{r[0]} {r[1]}' for r in rows) or 'quiet for now')+'.')

async def mymemory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Show bounded memory in the appropriate context."""
    db=context.application.bot_data.get('oracle_db'); u=update.effective_user
    if not db or not u:return
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,)); gid=int(row[0]) if row else 0
    if not gid:await update.effective_message.reply_text("☾ We haven't built a memory together yet.");return
    profile=await MemoryEngine(db).get(u.id,gid); items=list(profile.interests[:2])+list(profile.wins[:2])+list(profile.themes[:2]); await update.effective_message.reply_text('☾ What I remember\n'+('\n'.join('• '+x for x in items) if items else 'Nothing heavy stored. Just the moments that mattered.'))

async def forget(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Deactivate matching memory for the requesting member."""
    db=context.application.bot_data.get('oracle_db'); u=update.effective_user
    if not db or not u or not context.args:await update.effective_message.reply_text('Tell me what to forget: /forget <topic>');return
    gid=update.effective_chat.id if update.effective_chat.type!='private' else 0
    if not gid:
        row=await db.fetchone("SELECT group_id FROM members WHERE user_id=? ORDER BY last_seen DESC LIMIT 1",(u.id,));gid=int(row[0]) if row else 0
    n=await db.delete_memories_matching(u.id,gid,' '.join(context.args)) if gid else 0;await update.effective_message.reply_text('☾ Forgotten.' if n else "☾ I couldn't find that memory.")

async def quiet(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Silence ambient replies for two hours for an administrator."""
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}: await context.application.bot_data['oracle_db'].set_cooldown('group',str(update.effective_chat.id),'ambient',__import__('time').time()+7200); await update.effective_message.reply_text('☾ Quiet mode. I will stay out for two hours.')

async def wake(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Wake ambient replies for an administrator."""
    if update.effective_chat and update.effective_user:
        m=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if m.status in {'administrator','creator'}: await context.application.bot_data['oracle_db'].execute("DELETE FROM cooldowns WHERE scope='group' AND scope_id=? AND cooldown_type='ambient'",(str(update.effective_chat.id),)); await update.effective_message.reply_text("☾ I'm awake.")

async def house(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Open the deployed Telegram Mini App using the configured public URL."""
    url=_house_url()
    if not url:
        await update.effective_message.reply_text('☾ Oracle House is not configured yet.')
        return
    await update.effective_message.reply_text('☾ *Oracle House*\n\nA quieter room for your memories, achievements, group pulse and games.',parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Enter the House 🌙',web_app=WebAppInfo(url=url))]]))
