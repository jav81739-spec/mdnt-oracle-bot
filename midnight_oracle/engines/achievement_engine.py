"""Natural social achievements for Midnight Oracle."""
from __future__ import annotations
from ..database import Database, now_ts

ACHIEVEMENTS={
 'night_owl':('🌙 Night Owl','Active after 1AM three times',False),
 'comfort_person':('🫂 Comfort Person','Others vented to them 3+ times',False),
 'chaos_agent':('🎭 Chaos Agent','Started 5+ chaotic conversations',False),
 'philosopher':('🧠 Philosopher','Asked 3+ deep questions naturally',False),
 'truth_dealer':('🃏 Truth Dealer','Answered /truth 5+ times',False),
 'regular':('☕ Regular','Active for 30 consecutive days',False),
 'ghost':('👻 Ghost','Disappeared for 7 days then returned',True),
 'instigator':('🔥 Instigator','Triggered 3+ Oracle Moments',False),
 'quiet_observer':('🕯 Quiet Observer','Read-only for 14 days, then said something perfect',True),
 'oracle_whisperer':('☾ Oracle Whisperer','Oracle replied to them 20+ times naturally',True),
}

class AchievementEngine:
    """Evaluate milestone events and persist each badge exactly once."""
    def __init__(self,db:Database)->None:
        """Bind the engine to SQLite."""; self.db=db
    async def evaluate(self,user_id:int,group_id:int,event:str)->list[str]:
        """Evaluate one significant event and return newly unlocked keys."""
        row=await self.db.fetchone("SELECT interaction_count,last_seen,created_at FROM members WHERE user_id=? AND group_id=?",(user_id,group_id))
        if not row:return []
        count=int(row[0]); keys=[]
        if event=='night' and count>=3: keys.append('night_owl')
        if event=='comfort' and count>=3: keys.append('comfort_person')
        if event=='chaos' and count>=5: keys.append('chaos_agent')
        if event=='deep_question' and count>=3: keys.append('philosopher')
        if event=='truth_answer' and count>=5: keys.append('truth_dealer')
        if count>=30: keys.append('regular')
        if event=='return_after_absence': keys.append('ghost')
        if event=='oracle_moment_trigger': keys.append('instigator')
        if event=='quiet_return': keys.append('quiet_observer')
        if event=='oracle_reply' and count>=20: keys.append('oracle_whisperer')
        unlocked=[]
        for key in keys:
            meta=ACHIEVEMENTS.get(key)
            if not meta:continue
            try:
                await self.db.execute("INSERT INTO achievements(user_id,group_id,achievement_key,achieved_at,is_secret,is_revealed) VALUES(?,?,?,?,?,?)",(user_id,group_id,key,now_ts(),int(meta[2]),1))
                unlocked.append(key)
            except Exception: pass
        return unlocked
    async def announce(self,achievement_key:str,member:object,group_id:int)->str:
        """Format one restrained achievement announcement."""
        name=getattr(member,'preferred_name',None) or getattr(member,'first_name',None) or 'Someone'; meta=ACHIEVEMENTS[achievement_key]
        if meta[2]: return f"☾ There are things Oracle keeps track of quietly.\n{name} just discovered one: {meta[0]}."
        return f"☾ {name} just became a {meta[0]}.\n{meta[1]} — Oracle noticed."
