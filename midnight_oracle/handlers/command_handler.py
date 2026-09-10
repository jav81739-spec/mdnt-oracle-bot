"""Telegram commands for Midnight Oracle, preserving the original public surface."""
from __future__ import annotations
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from ..generators.truth_generator import question
from ..memory_engine import MemoryEngine

def _house_url() -> str:return (os.getenv("ORACLE_WEBAPP_URL") or os.getenv("ORACLE_MINI_APP_URL") or os.getenv("MINI_APP_URL") or "").strip()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    user=update.effective_user
    name=f"@{user.username}" if user and user.username else (user.first_name if user else "friend")
    if update.effective_chat and update.effective_chat.type=="private":
        text=f"""☾ <b>MIDNIGHT ORACLE</b>

<b>The room is open.</b>
──────────────
Hey, <b>{name}</b>.

No ceremony needed. Talk to me, start a game, ask for a reading, or bring whatever is keeping you awake.

<i>Some nights need answers. Some only need company.</i>

⌁ <b>/help</b>  open the rooms"""
    else:
        text=f"""☾ <b>MIDNIGHT ORACLE</b>

<b>Midnight has arrived.</b>
──────────────
<b>{name}</b> is here.

I'll stay quiet until the room gives me a reason to speak.

<i>Good conversations don't need an announcement.</i>"""
    await update.effective_message.reply_text(text,parse_mode="HTML")

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    text="""☾ <b>MIDNIGHT ORACLE</b>
<i>Conversation, games, readings, chaos.</i>
──────────────

<b>⌁ READINGS</b>
<code>/oracle</code> <code>/aura</code> <code>/vibecheck</code> <code>/identity</code> <code>/shadow</code> <code>/element</code> <code>/corecode</code>
<code>/universe</code> <code>/ritual</code> <code>/duality</code> <code>/nightreport</code> <code>/sigil</code> <code>/glitch</code>

<b>⌁ CONVERSATION</b>
<code>/chat</code> <code>/persona</code> <code>/vent</code> <code>/checkin</code> <code>/streakcheck</code>

<b>⌁ GAMES</b>
<code>/quiz</code> <code>/truth</code> <code>/dare</code> <code>/wyr</code> <code>/nhie</code> <code>/rps</code>
<code>/riddle</code> <code>/riddleanswer</code> <code>/scramble</code> <code>/unscramble</code> <code>/guess</code> <code>/leaderboard</code>
<code>/dice</code> <code>/darts</code> <code>/basketball</code> <code>/bowling</code> <code>/football</code> <code>/slot</code>
<code>/hangman</code> <code>/hangmanguess</code> <code>/tictactoe</code> <code>/ttt</code> <code>/wordchain</code> <code>/chainword</code>
<code>/trivia</code> <code>/wordle</code> <code>/wordleguess</code> <code>/ratethis</code> <code>/impostor</code> <code>/revealimpostor</code>

<b>⌁ PEOPLE</b>
<code>/bestie</code> <code>/duo</code> <code>/friendship</code> <code>/ship</code> <code>/tagbestie</code> <code>/squad</code> <code>/loyalty</code>
<code>/hug</code> <code>/pat</code> <code>/highfive</code> <code>/slap</code> <code>/kiss</code> <code>/poke</code> <code>/cuddle</code> <code>/wave</code> <code>/bite</code> <code>/tickle</code>

<b>⌁ MATCHMAKING</b>
<code>/matchmaker</code> <code>/randomship</code> <code>/secretadmirer</code> <code>/crush</code> <code>/clearcrush</code>

<b>⌁ CHAOS</b>
<code>/roast</code> <code>/compliment</code> <code>/8ball</code> <code>/vibe</code> <code>/quote</code> <code>/poll</code> <code>/rank</code>

<b>⌁ UTILITY</b>
<code>/id</code> <code>/info</code> <code>/remind</code> <code>/groupinfo</code> <code>/afk</code> <code>/report</code>

<b>⌁ STATS · ECONOMY</b>
<code>/stats</code> <code>/topactive</code> <code>/msgcount</code> <code>/joined</code> <code>/left</code>
<code>/daily</code> <code>/balance</code> <code>/rob</code> <code>/gamble</code> <code>/richest</code>

<b>⌁ MARRIAGE · SHOP</b>
<code>/marry</code> <code>/accept</code> <code>/divorce</code> <code>/profile</code> <code>/work</code> <code>/chests</code>
<code>/shop</code> <code>/buy</code> <code>/inventory</code> <code>/gift</code> <code>/settings</code>

<b>⌁ TIME CAPSULE</b>
<code>/timecapsule</code> <code>/capsules</code>

<b>⌁ DEATH GAMES</b>
<code>/survive</code> <code>/revive</code> <code>/deathstatus</code> <code>/roulette</code> <code>/deathgame</code> <code>/joingame</code>
<code>/startround</code> <code>/vote</code> <code>/endgame</code>

<b>⌁ CORE</b>
<code>/memory</code> <code>/mymemory</code> <code>/forget</code> <code>/quiet</code> <code>/wake</code> <code>/tod</code>
<code>/predict</code> <code>/predictions</code> <code>/house</code>

──────────────
<i>Private and owner controls stay private.</i>"""
    await update.effective_message.reply_text(text,parse_mode="HTML")

async def oracle(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    await update.effective_message.reply_text("☾ <b>I’m listening.</b>\n──────────────\nTell me what’s actually on your mind.\n\n<i>No polished version required.</i>",parse_mode="HTML")
async def truth(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:await update.effective_message.reply_text(f"☾ {question(context.args[0] if context.args else 'light')}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Answer',callback_data='truth:answer'),InlineKeyboardButton('Pass',callback_data='truth:pass')]]))

async def truth_callback(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    query=update.callback_query
    if not query:return
    action=(query.data or "").split(":",1)[-1]
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    if action=="answer":
        await query.message.reply_text("☾ Go on. I'm listening. No pressure to make it sound better than it is.")
    elif action=="pass":
        await query.message.reply_text("☾ Fair. The Oracle won't push. 🌙")

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
