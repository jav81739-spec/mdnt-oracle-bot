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
from ..engines.joke_engine import JokeEngine
from ..engines.group_identity_engine import GroupIdentityEngine
from ..engines.achievement_engine import AchievementEngine
from ..handlers.sticker_handler import StickerHandler
from ..voice_engine import VoiceEngine
from middleware.cooldown import cooldown_seconds, is_cooling
from middleware.recent_buffer import load_recent, save_recent
from middleware.alert import soft_alert

class MessageRouter:
    """Coordinate direct summons, DM chat, ambient friendship, memory, media and voice."""
    def __init__(self, engine: FriendEngine, memory: MemoryEngine, mood: MoodEngine, replies: ReplyGenerator | None = None) -> None:
        self.engine=engine; self.memory=memory; self.mood=mood; self.replies=replies or ReplyGenerator(); self.recent={}; self.voice=VoiceEngine()
        db=getattr(engine,'db',None); self.jokes=JokeEngine(db) if db else None; self.identity=GroupIdentityEngine(db) if db else None; self.achievements=AchievementEngine(db) if db else None; self.stickers=StickerHandler(db) if db else None
    async def _maybe_voice(self,message,chat_id,user_id,text,reply,direct,private):
        """Let Oracle occasionally speak when voice adds emotional/contextual value."""
        try:
            decision=self.voice.decide(chat_id=chat_id,user_id=user_id,text=text,direct=direct,private=private)
            if not decision.should_send:return
            audio=await self.voice.synthesize(reply)
            if audio is None:return
            try:
                await message.reply_voice(voice=audio,caption='☾ Midnight')
                self.voice.record(chat_id,user_id,reply)
            finally:
                audio.close()
        except Exception as exc:
            await soft_alert(None,'voice_delivery',exc)
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
    async def handle(self,update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
        try:
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
            now=datetime.now(); signal=self.mood.estimate(text); ctx=GroupContext(str(user.id),str(group_id),list(recent)[-10:],now.hour,now.hour>=23 or now.hour<3,group_name,profile.relationship_tier,profile.preferred_name or user.first_name or 'friend',now_ts(),(' | '.join(list(profile.themes[:2])+list(profile.worries[:1]))) or 'none')
            if private:
                reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet); await message.reply_text(reply); await self._maybe_voice(message,group_id,user.id,text,reply,True,True); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.jokes:
                await self.jokes.observe(text,user.id,group_id); callback=await self.jokes.detect_callback_opportunity(text,group_id)
                if callback and not direct and not await db.cooldown_active('group',str(group_id),'ambient'):
                    await message.reply_text(callback); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.identity: await self.identity.update(group_id,text,signal)
            if direct:
                reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet); await message.reply_text(reply); await self._maybe_voice(message,group_id,user.id,text,reply,True,False); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); await self._announce_achievements(message,user,group_id,'oracle_reply'); await self._hidden_surprise(message,group_id,user.id,text); return
            if self.stickers:
                media=await self.stickers.evaluate(message,signal,ctx)
                if media.should_send:
                    if media.sticker_id: await message.reply_sticker(media.sticker_id)
                    elif media.reaction_emoji: await context.bot.set_message_reaction(group_id,message.message_id,reaction=[ReactionTypeEmoji(media.reaction_emoji)])
                    await self.stickers.record(group_id,'contextual',media.sticker_id); await self.memory.observe(user.id,group_id,ctx.sender_name,text,True); recent.append(text); await save_recent(storage_client,str(group_id),recent); await self._hidden_surprise(message,group_id,user.id,text); return
            decision=await self.engine.process_message(message,ctx); await self.memory.observe(user.id,group_id,ctx.sender_name,text,decision.should_reply or signal.social>=0.5); recent.append(text); await save_recent(storage_client,str(group_id),recent)
            if decision.should_reply:
                reply=await self.replies.generate(group_name,ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet); await message.reply_text(reply); await self._maybe_voice(message,group_id,user.id,text,reply,False,False); await self._announce_achievements(message,user,group_id,'oracle_reply'); await self._hidden_surprise(message,group_id,user.id,text)
        except Exception as exc:
            application=getattr(context,'application',None); storage_client=getattr(application,'bot_data',{}).get('storage_client') if application else None; await soft_alert(storage_client,'message_router',exc)
    @staticmethod
    def _is_direct_summon(text,context):
        low=text.casefold(); username=str(getattr(getattr(context,'bot',None),'username','') or '').casefold(); return 'oracle' in low or 'midnight' in low or (username and f'@{username}' in low)
