"""Canonical Midnight Oracle message router — DM + group human chat."""
from __future__ import annotations
from datetime import datetime
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine, GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..generators.reply_generator import ReplyGenerator
from ..database import now_ts
from ..chat_context import analyze_message
from ..engines.joke_engine import JokeEngine
from ..engines.group_identity_engine import GroupIdentityEngine
from ..engines.achievement_engine import AchievementEngine
from ..handlers.sticker_handler import StickerHandler
from ..handlers.streaming_draft import TelegramDraftStream
from middleware.cooldown import cooldown_seconds, is_cooling
from middleware.recent_buffer import load_recent, save_recent
from middleware.alert import soft_alert

class MessageRouter:
    """Coordinate direct summons, DM chat, ambient friendship, memory, media and achievements."""
    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine, replies: ReplyGenerator | None = None) -> None:
        self.engine=engine; self.memory=memory; self.mood=mood; self.replies=replies or ReplyGenerator(); self.recent={}
        db=getattr(engine,'db',None); self.jokes=JokeEngine(db) if db else None; self.identity=GroupIdentityEngine(db) if db else None; self.achievements=AchievementEngine(db) if db else None; self.stickers=StickerHandler(db) if db else None

    async def _announce_achievements(self,message,member,group_id,event):
        if not self.achievements:return
        try:
            user_id=int(getattr(member,'user_id',getattr(member,'id',0)))
            for key in await self.achievements.evaluate(user_id,group_id,event): await message.reply_text(await self.achievements.announce(key,member,group_id))
        except Exception as exc: await soft_alert(None,'achievement_announce',exc)

    async def _hidden_surprise(self,message,chat_id,user_id,text):
        try:
            if abs(hash(f'{chat_id}:{user_id}:{text[:96]}'))%37!=11:return
            choices=('🌙 _tiny midnight signal: Oracle noticed that one._','✦ _filed quietly in the midnight archives._','🖤 _some moments deserve a little extra notice._')
            await message.reply_text(choices[abs(hash(text))%len(choices)])
        except Exception as exc: await soft_alert(None,'hidden_surprise',exc)

    async def _stream_private_reply(self, context, chat_id, draft_id, group_name, ctx, text, signal, recent_context, conversation_context):
        stream = TelegramDraftStream(context.bot, chat_id, draft_id)
        await stream.thinking()
        parts: list[str] = []
        async for delta in self.replies.stream(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet,recent_context,conversation_context):
            parts.append(delta)
            await stream.push(''.join(parts))
        reply = self.replies._clean(''.join(parts))
        await stream.finish()
        return reply

    async def handle(self,update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
        try:
            message=update.effective_message; chat=update.effective_chat; user=update.effective_user
            if not message or not chat or not user or bool(getattr(user,'is_bot',False)):return
            text=(message.text or message.caption or '').strip()
            if not text or text.startswith('/'):return
            private=chat.type=='private'; group=chat.type in {'group','supergroup'}
            if not private and not group:return
            direct=private or self._is_direct_summon(text,context,message)
            if is_cooling(f'{chat.id}:{user.id}',cooldown_seconds(chat.type,direct)):return
            application=getattr(context,'application',None); bot_data=getattr(application,'bot_data',{}) if application else {}; storage_client=bot_data.get('storage_client'); db=getattr(self.engine,'db',None)
            if not db:return
            group_id=chat.id; group_name=(chat.title or 'Midnight Oracle') if group else 'Midnight Oracle DM'
            await db.upsert_member(user.id,group_id,user.username or '',user.first_name or 'friend')
            profile=await self.memory.get(user.id,group_id); recent=await load_recent(storage_client,str(group_id)); self.recent[group_id]=recent
            recent_context=list(recent)[-8:]
            chat_context=analyze_message(text,direct_address=direct,reply_to_message=message.reply_to_message)
            context_parts=[f'language={chat_context.language}',f'intent={chat_context.intent_hint}',f'direct_address={str(chat_context.direct_address).lower()}']
            if chat_context.reply_to_text:
                context_parts.append(f'reply_to={chat_context.reply_to_name or "someone"}: {chat_context.reply_to_text}')
            conversation_context='; '.join(context_parts)
            now=datetime.now(); signal=self.mood.estimate(text); ctx=GroupContext(str(user.id),str(group_id),list(recent)[-10:],now.hour,now.hour>=23 or now.hour<3,group_name,profile.relationship_tier,profile.preferred_name or user.first_name or 'friend',now_ts(),(' | '.join(list(profile.themes[:2])+list(profile.worries[:1]))) or 'none')
            if private:
                try: await context.bot.send_chat_action(chat_id=group_id,action='typing')
                except Exception: pass
                draft_id = int((message.message_id << 1) | 1)
                try:
                    reply=await self._stream_private_reply(context,group_id,draft_id,group_name,ctx,text,signal,recent_context,conversation_context)
                except Exception:
                    reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet,recent_context,conversation_context)
                await message.reply_text(reply); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(f'{ctx.sender_name}: {text}'); recent.append(f'Oracle: {reply}'); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.jokes:
                await self.jokes.observe(text,user.id,group_id); callback=await self.jokes.detect_callback_opportunity(text,group_id)
                if callback and not direct and not await db.cooldown_active('group',str(group_id),'ambient'):
                    await message.reply_text(callback); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(f'{ctx.sender_name}: {text}'); recent.append(f'Oracle: {callback}'); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.identity: await self.identity.update(group_id,text,signal)
            if direct:
                try: await context.bot.send_chat_action(chat_id=group_id,action='typing')
                except Exception: pass
                reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet,recent_context,conversation_context); await message.reply_text(reply); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(f'{ctx.sender_name}: {text}'); recent.append(f'Oracle: {reply}'); await save_recent(storage_client,str(group_id),recent); await self._announce_achievements(message,user,group_id,'oracle_reply'); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.stickers:
                media=await self.stickers.evaluate(message,signal,ctx)
                if media.should_send:
                    if media.sticker_id: await message.reply_sticker(media.sticker_id)
                    elif media.reaction_emoji: await context.bot.set_message_reaction(group_id,message.message_id,reaction=[ReactionTypeEmoji(media.reaction_emoji)])
                    await self.stickers.record(group_id,'contextual',media.sticker_id); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(f'{ctx.sender_name}: {text}'); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            decision=await self.engine.process_message(message,ctx); await self.memory.observe(user.id,group_id,ctx.sender_name,text,decision.should_reply or signal.social>=0.5); recent.append(f'{ctx.sender_name}: {text}')
            if decision.should_reply:
                try: await context.bot.send_chat_action(chat_id=group_id,action='typing')
                except Exception: pass
                reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet,recent_context,conversation_context); await message.reply_text(reply); recent.append(f'Oracle: {reply}'); await self._announce_achievements(message,user,group_id,'oracle_reply'); await self._hidden_surprise(message,group_id,user.id,text)
            await save_recent(storage_client,str(group_id),recent)
        except Exception as exc:
            application=getattr(context,'application',None); storage_client=getattr(application,'bot_data',{}).get('storage_client') if application else None; await soft_alert(storage_client,'message_router',exc)

    @staticmethod
    def _is_direct_summon(text,context,message):
        low=text.casefold().strip(); username=str(getattr(getattr(context,'bot',None),'username','') or '').casefold()
        if username and f'@{username}' in low:return True
        replied=getattr(message,'reply_to_message',None); replied_user=getattr(replied,'from_user',None); bot_id=getattr(getattr(context,'bot',None),'id',None)
        if replied_user and bot_id and getattr(replied_user,'id',None)==bot_id:return True
        trigger_phrases=('hey oracle','oracle suno','oracle bhai','oracle bro','oracle listen','midnight suno','midnight bhai','midnight bro','hey midnight')
        return low in {'oracle','midnight'} or any(low==p or low.startswith(p+' ') for p in trigger_phrases)
