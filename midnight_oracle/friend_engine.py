"""Core observe → understand → score → cooldown → speak decision layer."""
from __future__ import annotations
import random,time
from dataclasses import dataclass
from telegram import Message
from .config import AMBIENT_ENGAGEMENT_RATE,ENGAGEMENT_THRESHOLD,MAX_AMBIENT_REPLIES_PER_HOUR,PER_MEMBER_COOLDOWN_SECONDS,PER_GROUP_COOLDOWN_SECONDS
from .database import Database
from .generators.reply_generator import ReplyGenerator
from .mood_engine import MoodEngine
from .utils.cooldown import CooldownManager

@dataclass(frozen=True)
class GroupContext:
    """Bounded context required for one social decision."""
    sender:str;group_id:str;recent_messages:list[str];hour:int;is_late_night:bool;group_name:str='';relationship_tier:str='new';sender_name:str='friend';now:float=0.0;memory_snippet:str='none'
@dataclass(frozen=True)
class EngineDecision:
    """Outcome of a FriendEngine evaluation."""
    should_reply:bool;reply_text:str|None;reason:str

class FriendEngine:
    """Provide conservative ambient friendship without keyword-only triggering."""
    _TIRED=("thak gaya","thak gya","thak gayi","tired","exhausted","neend aa rahi","bahut kaam","bohot kaam","bahut mehnat","burnt out","drained")
    _FRUSTRATED=("kya bakwas","irritating","fed up","nahi ho raha","nhi ho raha","frustrated","annoying","dimag kharab","pak gaya","pak gayi")
    _LONELY=("akela","akeli","bore ho raha","bore ho rahi","lonely","alone","koi nahi","nobody","no one")
    _VICTORY=("ho gaya","finally","khatam","cleared","got it","done","finished","we did it","yess","yes")
    _VULNERABLE=("nervous","scared","darr","pata nahi","worried","tension","anxious","hurt")
    _HUMOUR=("haha","hahaha","lol","lmao","😂","🤣","💀","chai","coffee")
    def __init__(self,db:Database,mood_engine:MoodEngine|None=None,reply_generator:ReplyGenerator|None=None,seed:int|None=None)->None:
        """Initialize the decision engine with persistent cooldowns and generators.""";self.db=db;self.cooldowns=CooldownManager(db);self.mood=mood_engine or MoodEngine();self.replies=reply_generator or ReplyGenerator();self.rng=random.Random(seed);self._last_sender={};self._hourly={}
    async def process_message(self,message:Message,context:GroupContext)->EngineDecision:
        """Evaluate one non-command group message and never propagate an internal failure."""
        try:
            text=(message.text or message.caption or '').strip()
            if not text:return EngineDecision(False,None,'no_text')
            if context.group_id=='0':return EngineDecision(False,None,'not_a_group')
            uid=message.from_user.id if message.from_user else 0;signal=self.mood.observe(uid,int(context.group_id),text);score,reasons=self._score(text,context,signal)
            allowed,reason=await self.cooldowns.can_ambient_reply(int(context.group_id),uid)
            if not allowed:return EngineDecision(False,None,reason)
            if self._last_sender.get(context.group_id)==context.sender:return EngineDecision(False,None,'same_sender_twice')
            now=context.now or time.time();bucket=self._hourly.setdefault(context.group_id,[]);bucket[:]=[x for x in bucket if now-x<3600]
            if len(bucket)>=MAX_AMBIENT_REPLIES_PER_HOUR:return EngineDecision(False,None,'hourly_cap')
            if score<ENGAGEMENT_THRESHOLD:return EngineDecision(False,None,'score_below_threshold')
            if self.rng.random()>AMBIENT_ENGAGEMENT_RATE:return EngineDecision(False,None,'probabilistic_silence')
            reply=await self.replies.generate(context.group_name or 'Midnight Oracle',context.sender_name,context.relationship_tier,text,signal.summary(),str(context.hour),context.is_late_night,context.memory_snippet);bucket.append(now);self._last_sender[context.group_id]=context.sender;await self.cooldowns.set('group',context.group_id,'ambient',PER_GROUP_COOLDOWN_SECONDS);await self.cooldowns.set('member',f'{context.group_id}:{context.sender}','ambient',PER_MEMBER_COOLDOWN_SECONDS);return EngineDecision(True,reply,'engaged:'+','.join(reasons))
        except Exception:return EngineDecision(False,None,'engine_error')
    def _score(self,text:str,context:GroupContext,signal)->tuple[int,list[str]]:
        """Calculate the configured 0–10 social-fit score.""";low=text.casefold();score,reasons=0,[];emotion=self._contains(low,self._TIRED+self._FRUSTRATED+self._VULNERABLE+self._LONELY)
        if self._contains(low,self._TIRED+self._FRUSTRATED):score+=3;reasons.append('emotion')
        if self._contains(low,self._LONELY):score+=3;reasons.append('connection')
        if self._contains(low,self._VICTORY):score+=3;reasons.append('celebration')
        if self._contains(low,self._HUMOUR) or '?' in text:score+=2;reasons.append('humour')
        if context.relationship_tier in {'known','close'}:score+=1;reasons.append('known')
        if '?' in text or any(w in low.split() for w in ('bhai','bro','yaar','guys','anyone','someone')):score+=1;reasons.append('outward')
        if getattr(signal,'social',0)>=.4:score+=2;reasons.append('social_fit')
        if context.is_late_night and (emotion or self._contains(low,self._VULNERABLE)):score+=2;reasons.append('late_emotion')
        recent=' '.join(context.recent_messages).casefold()
        if self._serious(recent,low):score-=4;reasons.append('serious')
        if context.recent_messages and any(x in recent for x in ('what do you think','what should i do','help me','can someone')):score-=4;reasons.append('directed_question')
        return max(0,min(10,score)),reasons
    @staticmethod
    def _contains(text:str,phrases:tuple[str,...])->bool:
        """Return whether any configured signal phrase occurs in normalized text.""";return any(p in text for p in phrases)
    @staticmethod
    def _serious(recent:str,current:str)->bool:
        """Detect conservative markers of a serious conversation.""";return any(x in recent or x in current for x in ('serious',"can't handle",'cannot handle','please help','hospital','family problem','passed away'))
