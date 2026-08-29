"""Main message router: preserve Phase 1 flow while adding Phase 2 social observation."""
from __future__ import annotations
from datetime import datetime
from telegram import Update,ReactionTypeEmoji
from telegram.ext import ContextTypes
from ..friend_engine import FriendEngine,GroupContext
from ..memory_engine import MemoryEngine
from ..mood_engine import MoodEngine
from ..generators.reply_generator import ReplyGenerator
from ..database import now_ts
from ..engines.joke_engine import JokeEngine
from ..engines.group_identity_engine import GroupIdentityEngine
from ..engines.achievement_engine import AchievementEngine
from ..handlers.sticker_handler import StickerHandler

class MessageRouter:
    """Coordinate direct summons, ambient friendship, memory, jokes, identity, achievements, and media."""
    def __init__(self,engine:FriendEngine,memory:MemoryEngine,mood:MoodEngine,replies:ReplyGenerator|None=None)->None:
        """Bind social engines when the supplied Phase 1 engine exposes persistence."""
        self.engine=engine;self.memory=memory;self.mood=mood;self.replies=replies or ReplyGenerator();self.recent={};db=getattr(engine,'db',None);self.jokes=JokeEngine(db) if db else None;self.identity=GroupIdentityEngine(db) if db else None;self.achievements=AchievementEngine(db) if db else None;self.stickers=StickerHandler(db) if db else None
    async def _announce_achievements(self,message,member,group_id,event:str)->None:
        """Announce only newly unlocked social achievements."""
        if not self.achievements:return
        try:
            user_id=int(getattr(member,'user_id',getattr(member,'id',0)))
            for key in await self.achievements.evaluate(user_id,group_id,event):
                await message.reply_text(await self.achievements.announce(key,member,group_id))
        except Exception:
            return
    async def handle(self,update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
        """Process one group text update without leaking internal exceptions."""
        try:
            message=update.effective_message;chat=update.effective_chat;user=update.effective_user
            if not message or not chat or not user or chat.type not in {'group','supergroup'}:return
            text=(message.text or message.caption or '').strip()
            if not text or text.startswith('/'):return
            db=getattr(self.engine,'db',None)
            if not db:return
            await db.execute("INSERT INTO group_profile(group_id,group_name,timezone,created_at) VALUES(?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET group_name=excluded.group_name",(chat.id,chat.title or '','Asia/Kolkata',now_ts()))
            await db.upsert_member(user.id,chat.id,user.username or '',user.first_name or 'friend');profile=await self.memory.get(user.id,chat.id);recent=self.recent.setdefault(chat.id,[]);now=datetime.now();signal=self.mood.estimate(text)
            ctx=GroupContext(str(user.id),str(chat.id),recent[-10:],now.hour,now.hour>=23 or now.hour<3,chat.title or '',profile.relationship_tier,profile.preferred_name or user.first_name or 'friend',now_ts(),(' | '.join(list(profile.themes[:2])+list(profile.worries[:1]))) or 'none')
            if self.jokes:
                await self.jokes.observe(text,user.id,chat.id)
                callback=await self.jokes.detect_callback_opportunity(text,chat.id)
                if callback and not await db.cooldown_active('group',str(chat.id),'ambient'):
                    await message.reply_text(callback)
                    await self.memory.observe(user.id,chat.id,ctx.sender_name,text,True)
                    recent.append(text);del recent[:-10]
                    await self._announce_achievements(message,user,chat.id,'oracle_reply')
                    return
            if self.identity:await self.identity.update(chat.id,text,signal)
            if self._is_direct_summon(text,context):
                reply=await self.replies.generate(chat.title or 'Midnight Oracle',ctx.sender_name,ctx.relationship_tier,text,signal.summary(),str(ctx.hour),ctx.is_late_night,ctx.memory_snippet);await message.reply_text(reply);await self.memory.observe(user.id,chat.id,ctx.sender_name,text,True);await self._announce_achievements(message,user,chat.id,'oracle_reply');return
            if self.stickers:
                media=await self.stickers.evaluate(message,signal,ctx)
                if media.should_send:
                    if media.sticker_id:await message.reply_sticker(media.sticker_id)
                    elif media.reaction_emoji:await context.bot.set_message_reaction(chat.id,message.message_id,reaction=[ReactionTypeEmoji(media.reaction_emoji)])
                    await self.stickers.record(chat.id,'contextual',media.sticker_id);await self.memory.observe(user.id,chat.id,ctx.sender_name,text,True);recent.append(text);del recent[:-10];return
            decision=await self.engine.process_message(message,ctx);await self.memory.observe(user.id,chat.id,ctx.sender_name,text,decision.should_reply or signal.social>=.5);recent.append(text);del recent[:-10]
            if decision.should_reply and decision.reply_text:
                await message.reply_text(decision.reply_text)
                await self._announce_achievements(message,user,chat.id,'oracle_reply')
        except Exception:return
    @staticmethod
    def _is_direct_summon(text:str,context:ContextTypes.DEFAULT_TYPE)->bool:
        """Detect explicit Oracle summons without affecting ambient scoring."""
        low=text.casefold();username=str(getattr(getattr(context,'bot',None),'username','') or '').casefold();return 'oracle' in low or 'midnight' in low or (username and f'@{username}' in low)
