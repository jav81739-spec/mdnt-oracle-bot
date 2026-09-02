"""Persistent, defensive moderation handlers for Midnight Oracle."""
from __future__ import annotations
from telegram import ChatPermissions, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from core.storage import storage

async def _is_admin(update:Update,context:ContextTypes.DEFAULT_TYPE)->bool:
    try:
        member=await context.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        return member.status in ('administrator','creator')
    except TelegramError:return False

async def _bot_can_restrict(update,context)->bool:
    try:
        me=await context.bot.get_me();member=await context.bot.get_chat_member(update.effective_chat.id,me.id)
        return bool(getattr(member,'can_restrict_members',False) or member.status=='creator')
    except TelegramError:return False

async def _target(update):return update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else None
async def _target_is_admin(update,context,target_id:int)->bool:
    try:return (await context.bot.get_chat_member(update.effective_chat.id,target_id)).status in ('administrator','creator')
    except TelegramError:return True

def _warning_key(chat_id:int,user_id:int)->str:return f"moderation:warnings:{chat_id}:{user_id}"
def _rules_key(chat_id:int)->str:return f"moderation:rules:{chat_id}"

async def mute(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /mute')
    if target.id==context.bot.id or await _target_is_admin(update,context,target.id):return await update.message.reply_text("☾ I won't restrict an admin.")
    if not await _bot_can_restrict(update,context):return await update.message.reply_text("☾ I don't have permission to mute members here.")
    try:await context.bot.restrict_chat_member(update.effective_chat.id,target.id,ChatPermissions(can_send_messages=False));await update.message.reply_text(f'🔇 Muted {target.first_name}')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me mute that member.")

async def unmute(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /unmute')
    if not await _bot_can_restrict(update,context):return await update.message.reply_text("☾ I don't have permission to change member restrictions here.")
    try:await context.bot.restrict_chat_member(update.effective_chat.id,target.id,ChatPermissions(can_send_messages=True));await update.message.reply_text(f'🔊 Unmuted {target.first_name}')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me unmute that member.")

async def ban(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /ban')
    if target.id==context.bot.id or await _target_is_admin(update,context,target.id):return await update.message.reply_text("☾ I won't ban an admin.")
    if not await _bot_can_restrict(update,context):return await update.message.reply_text("☾ I don't have permission to ban members here.")
    try:await context.bot.ban_chat_member(update.effective_chat.id,target.id);await update.message.reply_text(f'🚫 Banned {target.first_name}')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me ban that member.")

async def kick(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /kick')
    if target.id==context.bot.id or await _target_is_admin(update,context,target.id):return await update.message.reply_text("☾ I won't kick an admin.")
    if not await _bot_can_restrict(update,context):return await update.message.reply_text("☾ I don't have permission to kick members here.")
    try:await context.bot.ban_chat_member(update.effective_chat.id,target.id);await context.bot.unban_chat_member(update.effective_chat.id,target.id);await update.message.reply_text(f'👢 Kicked {target.first_name}')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me kick that member.")

async def warn(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /warn')
    if target.id==context.bot.id or await _target_is_admin(update,context,target.id):return await update.message.reply_text("☾ I won't warn an admin.")
    chat_id=update.effective_chat.id;key=_warning_key(chat_id,target.id)
    async with storage.lock(f'warning:{chat_id}:{target.id}') as acquired:
        if not acquired:return await update.message.reply_text('⏳ Moderation is busy — try again.')
        raw=await storage.get(key,'0')
        try:count=int(raw or 0)+1
        except (TypeError,ValueError):count=1
        if not await storage.set(key,str(count)):return await update.message.reply_text("☾ I couldn't save that warning.")
    await update.message.reply_text(f'⚠️ {target.first_name} warned ({count}/3)')
    if count>=3:await ban(update._replace(message=update.message),context) if False else await _auto_ban(context,chat_id,target)

async def _auto_ban(context,chat_id,target):
    try:await context.bot.ban_chat_member(chat_id,target.id);await context.bot.send_message(chat_id,f'{target.first_name} reached 3 warnings and was banned.')
    except TelegramError:await context.bot.send_message(chat_id,"☾ Three warnings reached, but Telegram did not allow the ban.")

async def show_rules(update,context):
    rules=await storage.get(_rules_key(update.effective_chat.id),'') or 'No rules set yet. Admins can use /setrules to add them.';await update.message.reply_text(f'📜 Group Rules:\n{rules}')
async def check_warnings(update,context):
    target=await _target(update) or update.effective_user;raw=await storage.get(_warning_key(update.effective_chat.id,target.id),'0')
    try:count=int(raw or 0)
    except (TypeError,ValueError):count=0
    await update.message.reply_text(f'⚠️ {target.first_name} has {count}/3 warnings')
async def clear_warnings(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    target=await _target(update)
    if not target:return await update.message.reply_text('Reply to the user with /clearwarns')
    await storage.delete(_warning_key(update.effective_chat.id,target.id));await update.message.reply_text(f'🧹 Warnings cleared for {target.first_name}')

async def pin(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    if not update.message.reply_to_message:return await update.message.reply_text('Reply to the message with /pin')
    try:await context.bot.pin_chat_message(update.effective_chat.id,update.message.reply_to_message.message_id);await update.message.reply_text('📌 Pinned.')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me pin that message.")
async def unpin(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    try:await context.bot.unpin_chat_message(update.effective_chat.id);await update.message.reply_text('📌 Unpinned.')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me unpin that message.")
async def _delete_later(context):
    try:await context.bot.delete_message(context.job.chat_id,context.job.data)
    except TelegramError:pass
async def purge(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    if not update.message.reply_to_message or not context.args:return await update.message.reply_text('Reply to a message with /purge [1-100]')
    try:count=int(context.args[0])
    except (TypeError,ValueError):return await update.message.reply_text('Usage: /purge [1-100]')
    if not 1<=count<=100:return await update.message.reply_text('Choose a purge count between 1 and 100.')
    chat_id=update.effective_chat.id;start_id=update.message.reply_to_message.message_id;deleted=0
    for msg_id in range(start_id,start_id+count):
        try:await context.bot.delete_message(chat_id,msg_id);deleted+=1
        except TelegramError:pass
    try:await update.message.delete()
    except TelegramError:pass
    confirmation=await context.bot.send_message(chat_id,f'🧹 Purged {deleted} messages')
    if context.job_queue:context.job_queue.run_once(_delete_later,when=5,chat_id=chat_id,data=confirmation.message_id)
async def set_rules(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    if not context.args:return await update.message.reply_text('Usage: /setrules [your rules text]')
    if not await storage.set(_rules_key(update.effective_chat.id),' '.join(context.args)[:4000]):return await update.message.reply_text("☾ I couldn't save those rules.")
    await update.message.reply_text('📜 Rules updated. Check them anytime with /rules')
async def lock(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    lock_type=context.args[0].lower() if context.args else 'all'
    if lock_type=='media':permissions=ChatPermissions(can_send_messages=True,can_send_photos=False,can_send_videos=False,can_send_other_messages=False)
    elif lock_type=='all':permissions=ChatPermissions(can_send_messages=False)
    else:return await update.message.reply_text('Usage: /lock media | /lock all')
    try:await context.bot.set_chat_permissions(update.effective_chat.id,permissions);await update.message.reply_text(f'🔒 Locked: {lock_type}')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me change group permissions.")
async def unlock(update,context):
    if not await _is_admin(update,context):return await update.message.reply_text('Admins only.')
    try:await context.bot.set_chat_permissions(update.effective_chat.id,ChatPermissions(can_send_messages=True,can_send_photos=True,can_send_videos=True,can_send_other_messages=True));await update.message.reply_text('🔓 Unlocked — normal permissions restored.')
    except TelegramError:await update.message.reply_text("☾ Telegram wouldn't let me restore permissions.")
