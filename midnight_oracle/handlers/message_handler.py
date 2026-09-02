"""Canonical Midnight Oracle message router for DMs and groups."""
from __future__ import annotations
from collections import deque
from datetime import datetime
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine, GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..generators.reply_generator import ReplyGenerator
from ..database import now_ts
from ..engines.joke_engine import JokeEngine
from ..engines.group_identity_engine import GroupIdentityEngine
from ..engines.achievement_engine import AchievementEngine
from ..handlers.sticker_handler import StickerHandler
from ..voice_engine import VoiceEngine
from ..voice_triggers import wants_voice
from ..media_brain import decide as media_decide, enabled as media_enabled
from middleware.cooldown import cooldown_seconds, is_cooling
from middleware.recent_buffer import load_recent, save_recent
from middleware.alert import soft_alert

class MessageRouter:
    """Coordinate one coherent conversation path: context, memory, voice and media."""
    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine, replies: ReplyGenerator | None = None) -> None:
        self.engine=engine; self.memory=memory; self.mood=mood; self.replies=replies or ReplyGenerator(); self.recent={}; self._seen_updates=deque(maxlen=4096)
        db=getattr(engine,'db',None); self.jokes=JokeEngine(db) if db else None; self.identity=GroupIdentityEngine(db) if db else None; self.achievements=AchievementEngine(db) if db else None; self.stickers=StickerHandler(db) if db else None; self.voice=VoiceEngine()

    async def _send_reply(self,update,message,context,reply:str,*,chat_id:int,user_id:int,text:str,direct:bool,private:bool)->None:
        explicit=wants_voice(text); voice_decision=self.voice.decide(chat_id=chat_id,user_id=user_id,text=text,direct=direct,private=private)
        if explicit and not voice_decision.should_send:
            voice_decision=voice_decision.__class__(True,'explicit_voice')
        if voice_decision.should_send:
            audio=await self.voice.synthesize(reply,voice='shimmer')
            if audio:
                try:
                    await message.reply_voice(voice=audio); self.voice.record(chat_id,user_id,reply); return
                except Exception as exc: await soft_alert(None,'voice_delivery',exc)
        await message.reply_text(reply)
        if media_enabled():
            try:
                media=media_decide(update,text=text)
                if media and media.kind=='gif':
                    from handlers.chat import get_gif_url
                    from core.oracle_media import send_additive_gif
                    url=await get_gif_url(media.query)
                    if url:
                        await send_additive_gif(context.bot,chat_id,url,reply_to_message_id=getattr(message,'message_id',None))
            except Exception as exc: await soft_alert(None,'media_delivery',exc)

    async def _announce_achievements(self,message,member,group_id,event):
        if not self.achievements:return
        try:
            user_id=int(getattr(member,'user_id',getattr(member,'id',0)))
            for key in await self.achievements.evaluate(user_id,group_id,event): await message.reply_text(await self.achievements.announce(key,member,group_id))
        except Exception as exc: await soft_alert(None,'achievement_announce',exc)

    async def _generate(self,group_name,ctx,text,signal,recent):
        return await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet,recent_context=list(recent)[-12:])

    async def handle(self,update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
        try:
            update_id=getattr(update,'update_id',None)
            if update_id is not None:
                if update_id in self._seen_updates:return
                self._seen_updates.append(update_id)
            message=update.effective_message; chat=update.effective_chat; user=update.effective_user
            if not message or not chat or not user or bool(getattr(user,'is_bot',False)):return
            text=(message.text or message.caption or '').strip()
            if not text or text.startswith('/'):return
            private=chat.type=='private'; group=chat.type in {'group','supergroup'}
            if not private and not group:return
            direct=private or self._is_direct_summon(text,context)
            if is_cooling(f'{chat.id}:{user.id}',cooldown_seconds(chat.type,direct)):return
            application=getattr(context,'application',None); bot_data=getattr(application,'bot_data',{}) if application else {}; storage_client=bot_data.get('storage_client'); db=getattr(self.engine,'db',None)
            if not db:return
            group_id=chat.id; group_name=(chat.title or 'Midnight Oracle') if group else 'Midnight Oracle DM'
            await db.upsert_member(user.id,group_id,user.username or '',user.first_name or 'friend')
            profile=await self.memory.get(user.id,group_id); recent=await load_recent(storage_client,str(group_id)); self.recent[group_id]=recent
            now=datetime.now(); signal=self.mood.estimate(text); ctx=GroupContext(str(user.id),str(group_id),list(recent)[-12:],now.hour,now.hour>=23 or now.hour<3,group_name,profile.relationship_tier,profile.preferred_name or user.first_name or 'friend',now_ts(),(' | '.join(list(profile.themes[:2])+list(profile.worries[:1]))) or 'none')
            if private:
                reply=await self._generate(group_name,ctx,text,signal,recent); await self._send_reply(update,message,context,reply,chat_id=group_id,user_id=user.id,text=text,direct=True,private=True); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); return
            if self.jokes:
                await self.jokes.observe(text,user.id,group_id); callback=await self.jokes.detect_callback_opportunity(text,group_id)
                if callback and not direct and not await db.cooldown_active('group',str(group_id),'ambient'):
                    await message.reply_text(callback); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); return
            if self.identity: await self.identity.update(group_id,text,signal)
            if direct:
                reply=await self._generate(group_name,ctx,text,signal,recent); await self._send_reply(update,message,context,reply,chat_id=group_id,user_id=user.id,text=text,direct=True,private=False); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); await self._announce_achievements(message,user,group_id,'oracle_reply'); return
            if self.stickers:
                media=await self.stickers.evaluate(message,signal,ctx)
                if media.should_send:
                    try:
                        if media.sticker_id: await message.reply_sticker(media.sticker_id)
                        elif media.reaction_emoji: await context.bot.set_message_reaction(group_id,message.message_id,reaction=[ReactionTypeEmoji(media.reaction_emoji)])
                        await self.stickers.record(group_id,'contextual',media.sticker_id)
                    except Exception as exc: await soft_alert(None,'sticker_delivery',exc)
            decision=await self.engine.process_message(message,ctx); await self.memory.observe(user.id,group_id,ctx.sender_name,text,decision.should_reply or signal.social>=0.5); recent.append(text); await save_recent(storage_client,str(group_id),recent)
            if decision.should_reply:
                reply=await self._generate(group_name,ctx,text,signal,recent); await self._send_reply(update,message,context,reply,chat_id=group_id,user_id=user.id,text=text,direct=False,private=False); await self._announce_achievements(message,user,group_id,'oracle_reply')
        except Exception as exc:
            application=getattr(context,'application',None); storage_client=getattr(application,'bot_data',{}).get('storage_client') if application else None; await soft_alert(storage_client,'message_router',exc)

    @staticmethod
    def _is_direct_summon(text,context):
        low=text.casefold().strip(); username=str(getattr(getattr(context,'bot',None),'username','') or '').casefold()
        if username and f'@{username}' in low:return True
        words={w.strip('.,!?():;[]{}') for w in low.split()}
        return 'oracle' in words or 'midnight' in words
