"""Bot-side Mini App data dispatcher."""
from __future__ import annotations
import json
from telegram import Update
from telegram.ext import ContextTypes
from ..utils.webapp_auth import validate_init_data

async def handle_webapp_data(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Validate WebApp initData and dispatch supported privacy-scoped actions."""
    try:
        raw=update.effective_message.web_app_data.data; payload=json.loads(raw); pairs=validate_init_data(str(payload.get('initData',''))); user=json.loads(pairs.get('user','{}')); uid=int(user['id']); action=str(payload.get('action','')); db=context.application.bot_data['oracle_db']; chat_id=int(payload.get('group_id') or 0)
        if action=='get_my_memory': data=await db.fetchall("SELECT memory_type,content,created_at FROM member_memory WHERE user_id=? AND group_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 20",(uid,chat_id))
        elif action=='get_achievements': data=await db.fetchall("SELECT achievement_key,achieved_at,is_secret,is_revealed FROM achievements WHERE user_id=? AND group_id=?",(uid,chat_id))
        elif action=='get_group_stats': data=await db.fetchone("SELECT humour_level,depth_level,activity_pattern,favourite_topics,quiet_periods,peak_hours FROM group_identity WHERE group_id=?",(chat_id,))
        elif action=='get_game_history': data=await db.fetchall("SELECT game_type,winner_user_id,summary,played_at FROM game_history WHERE group_id=? ORDER BY played_at DESC LIMIT 50",(chat_id,))
        elif action=='forget_topic': data={'deleted':await db.delete_memories_matching(uid,chat_id,str(payload.get('topic','')))}
        elif action=='update_preference': pref=str(payload.get('preference','lurker')); data=await db.execute("UPDATE members SET interaction_preference=? WHERE user_id=? AND group_id=?",(pref,uid,chat_id)); data={'ok':True}
        else:data={'error':'unsupported action'}
        await update.effective_message.reply_text('☾ House data is ready.')
    except Exception: await update.effective_message.reply_text('☾ House is quiet right now.')
