"""Conservative observe → understand → cooldown → speak decision layer."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from telegram import Message

from .config import AMBIENT_ENGAGEMENT_RATE, ENGAGEMENT_THRESHOLD, MAX_AMBIENT_REPLIES_PER_HOUR, PER_GROUP_COOLDOWN_SECONDS, PER_MEMBER_COOLDOWN_SECONDS
from .database import Database
from .generators.reply_generator import ReplyGenerator
from .mood_engine import MoodEngine
from .utils.cooldown import CooldownManager


@dataclass(frozen=True)
class GroupContext:
    sender: str; group_id: str; recent_messages: list[str]; hour: int; is_late_night: bool
    group_name: str = ""; relationship_tier: str = "new"; sender_name: str = "friend"; now: float = 0.0; memory_snippet: str = "none"


@dataclass(frozen=True)
class EngineDecision:
    should_reply: bool; reply_text: str | None; reason: str


class FriendEngine:
    """Ambient engagement is opt-in by conversational signal, never by randomness alone."""
    _TIRED=("thak gaya","thak gya","thak gayi","tired","exhausted","neend aa rahi","bahut kaam","bohot kaam","bahut mehnat","burnt out","drained")
    _FRUSTRATED=("kya bakwas","irritating","fed up","nahi ho raha","nhi ho raha","frustrated","annoying","dimag kharab","pak gaya","pak gayi")
    _LONELY=("akela","akeli","bore ho raha","bore ho rahi","lonely","alone","koi nahi","nobody","no one")
    _LOW_MOOD=("sad","udaas","low feel","feeling low","feel low","feeling down","empty feel","feel empty","miss kar raha","miss kar rahi","miss someone")
    _VICTORY=("ho gaya","finally","khatam","cleared","got it","done","finished","we did it","yess","yes")
    _VULNERABLE=("nervous","scared","darr","pata nahi","worried","tension","anxious","hurt")
    _HUMOUR=("haha","hahaha","lol","lmao","😂","🤣","💀","chai","coffee")
    _OUTWARD=("bhai","bro","yaar","guys","anyone","someone")
    _SERIOUS=("serious","can't handle","cannot handle","please help","hospital","family problem","passed away")

    def __init__(self,db:Database,mood_engine:MoodEngine|None=None,reply_generator:ReplyGenerator|None=None,seed:int|None=None)->None:
        self.db=db;self.cooldowns=CooldownManager(db);self.mood=mood_engine or MoodEngine();self.replies=reply_generator or ReplyGenerator();self.rng=random.Random(seed);self._last_sender={};self._hourly={}

    async def process_message(self,message:Message,context:GroupContext)->EngineDecision:
        try:
            text=(message.text or message.caption or "").strip()
            if not text:return EngineDecision(False,None,"no_text")
            if context.group_id=="0":return EngineDecision(False,None,"not_a_group")
            uid=message.from_user.id if message.from_user else 0;low=text.casefold();signal=self.mood.observe(uid,int(context.group_id),text);score,reasons=self._score(text,context,signal)
            allowed,reason=await self.cooldowns.can_ambient_reply(int(context.group_id),uid)
            if not allowed:return EngineDecision(False,None,reason)
            if self._last_sender.get(context.group_id)==context.sender:return EngineDecision(False,None,"same_sender_twice")
            if score<ENGAGEMENT_THRESHOLD:return EngineDecision(False,None,"score_below_threshold")
            if not self._ambient_opening(text,low,context,signal):return EngineDecision(False,None,"no_conversational_opening")
            now=context.now or time.time();bucket=self._hourly.setdefault(context.group_id,[]);bucket[:]=[stamp for stamp in bucket if now-stamp<3600]
            if len(bucket)>=MAX_AMBIENT_REPLIES_PER_HOUR:return EngineDecision(False,None,"hourly_cap")
            if self.rng.random()>AMBIENT_ENGAGEMENT_RATE:return EngineDecision(False,None,"probabilistic_silence")
            reply=await self.replies.generate(context.group_name or "Midnight Oracle",context.sender_name,context.relationship_tier,text,signal.summary(),str(context.hour),context.is_late_night,context.memory_snippet,context.recent_messages[-8:])
            if not reply.strip():return EngineDecision(False,None,"provider_unavailable")
            bucket.append(now);self._last_sender[context.group_id]=context.sender
            try:
                await self.cooldowns.set("group",context.group_id,"ambient",PER_GROUP_COOLDOWN_SECONDS);await self.cooldowns.set("member",f"{context.group_id}:{context.sender}","ambient",PER_MEMBER_COOLDOWN_SECONDS)
            except Exception:pass
            return EngineDecision(True,reply,"engaged:"+",".join(reasons))
        except Exception:return EngineDecision(False,None,"engine_error")

    def _score(self,text:str,context:GroupContext,signal)->tuple[int,list[str]]:
        low=text.casefold();score=0;reasons=[];emotion=self._contains(low,self._TIRED+self._FRUSTRATED+self._VULNERABLE+self._LONELY+self._LOW_MOOD)
        if self._contains(low,self._TIRED+self._FRUSTRATED):score+=3;reasons.append("emotion")
        if self._contains(low,self._LONELY):score+=3;reasons.append("connection")
        if self._contains(low,self._LOW_MOOD):score+=3;reasons.append("low_mood")
        if self._contains(low,self._VICTORY):score+=3;reasons.append("celebration")
        if self._contains(low,self._HUMOUR):score+=2;reasons.append("humour")
        if "?" in text:score+=2;reasons.append("question")
        if context.relationship_tier in {"known","close"}:score+=1;reasons.append("known")
        if self._contains(low,self._OUTWARD):score+=1;reasons.append("outward")
        if getattr(signal,"social",0)>=.4:score+=2;reasons.append("social_fit")
        if context.is_late_night and (emotion or self._contains(low,self._VULNERABLE)):score+=3;reasons.append("late_emotion")
        recent=" ".join(context.recent_messages).casefold()
        if self._serious(recent,low):score-=4;reasons.append("serious")
        if context.recent_messages and any(x in recent for x in ("what do you think","what should i do","help me","can someone")):score-=4;reasons.append("directed_question")
        return max(0,min(10,score)),reasons

    @staticmethod
    def _ambient_opening(text:str,low:str,context:GroupContext,signal)->bool:
        if "?" in text or any(token in low.split() for token in FriendEngine._OUTWARD):return True
        if any(token in low for token in FriendEngine._TIRED+FriendEngine._FRUSTRATED+FriendEngine._LONELY+FriendEngine._LOW_MOOD+FriendEngine._VULNERABLE+FriendEngine._VICTORY+FriendEngine._HUMOUR):return True
        return bool(getattr(signal,"social",0)>=.65 and len(context.recent_messages)>=2)

    @staticmethod
    def _contains(text:str,phrases:tuple[str,...])->bool:return any(phrase in text for phrase in phrases)
    @staticmethod
    def _serious(recent:str,current:str)->bool:return any(x in recent or x in current for x in FriendEngine._SERIOUS)
