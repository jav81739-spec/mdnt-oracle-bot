"""Complete five-round Word Scramble lifecycle."""
from __future__ import annotations
import json,random,re
from telegram import Message
from ..database import Database,now_ts

WORDS={'easy':['moon','rain','chai','game','star','book','home','night','smile','dream','heart','music','light','time'],'medium':['oracle','coffee','silence','friend','cricket','lantern','journey','morning','evening','mystery','thought','village','weather','picture'],'hard':['midnight','moonlight','friendship','conversation','adventure','beautiful','unexpected','philosophy','community','happiness','curiosity','memories']}

class WordScrambleGame:
    """Run a persistent five-round scramble with atomic first-answer scoring."""
    game_type='word_scramble';total_rounds=5;timeout_seconds=30
    def __init__(self,db:Database)->None:
        """Bind the game to SQLite.""";self.db=db
    @staticmethod
    def scramble(word:str)->str:
        """Shuffle letters and guarantee the result differs from the original."""
        chars=list(word);original=word.lower()
        if len(chars)<2:return word
        for _ in range(20):
            random.shuffle(chars);out=''.join(chars)
            if out.lower()!=original:return out
        return original[::-1]
    def _pick(self,used:list[str],round_no:int)->str:
        """Pick from the configured 2-easy/2-medium/1-hard distribution."""
        tier='easy' if round_no<=2 else ('medium' if round_no<=4 else 'hard');pool=[w for w in WORDS[tier] if w not in used] or WORDS[tier];return random.choice(pool)
    async def start(self,group_id:int,starter:object)->str:
        """Create a five-round session and return the first round prompt."""
        active=await self.db.fetchone("SELECT id FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1",(group_id,self.game_type))
        if active:return '☾ A scramble is already running.'
        word=self._pick([],1);state={'round':1,'total_rounds':5,'current_word':word,'current_scramble':self.scramble(word),'round_winner':None,'scores':{},'used_words':[word],'round_start_time':now_ts(),'awaiting_answer':True}
        await self.db.execute("INSERT INTO game_sessions(group_id,game_type,state,current_turn_user_id,started_at,is_active) VALUES(?,?,?,?,?,1)",(group_id,self.game_type,json.dumps(state),getattr(starter,'user_id',None),now_ts()));return self.prompt(state)
    @staticmethod
    def prompt(state:dict)->str:
        """Format the current round prompt.""";return f"☾ Round {state['round']}/5 — unscramble this:\n\n[ {state['current_scramble'].upper()} ]\n\nFirst correct answer wins the round. ⏱ 30 seconds."
    async def get_active(self,group_id:int):
        """Return the active scramble session.""";return await self.db.fetchone("SELECT * FROM game_sessions WHERE group_id=? AND game_type=? AND is_active=1 LIMIT 1",(group_id,self.game_type))
    async def submit_answer(self,group_id:int,user_id:int,name:str,answer:str)->tuple[bool,str|None,bool]:
        """Atomically accept the first correct answer and advance or finish the game."""
        row=await self.get_active(group_id)
        if not row:return False,None,False
        await self.db.db.execute('BEGIN IMMEDIATE')
        try:
            current=await self.db.db.execute('SELECT id,state,is_active FROM game_sessions WHERE id=?',(int(row['id']),));r=await current.fetchone()
            if not r or not r[2]:await self.db.db.rollback();return False,None,False
            state=json.loads(r[1]);norm=lambda s:re.sub(r'[^a-z0-9]','',str(s).casefold());
            if not state.get('awaiting_answer') or norm(answer)!=norm(state.get('current_word','')):await self.db.db.rollback();return False,None,False
            uid=str(user_id);scores=state.setdefault('scores',{});scores[uid]=int(scores.get(uid,0))+1;state['round_winner']=uid;state['awaiting_answer']=False
            await self.db.db.execute('UPDATE game_sessions SET state=? WHERE id=? AND is_active=1',(json.dumps(state),int(row['id'])));await self.db.db.commit()
            summary=' · '.join(f'{uid_}: {score}' for uid_,score in sorted(scores.items(),key=lambda x:(-x[1],x[0])))
            return True,f'✓ [{name}] got it — {state["current_word"]} 🎯\nScore: {summary}',state['round']>=state['total_rounds']
        except Exception:await self.db.db.rollback();raise
    async def next_round(self,group_id:int)->str|None:
        """Advance a finished round or close the game after round five."""
        row=await self.get_active(group_id)
        if not row:return None
        state=json.loads(row['state'])
        if state['round']>=state['total_rounds']:return await self.finish(group_id)
        state['round']+=1;state['round_winner']=None;state['awaiting_answer']=True;word=self._pick(state['used_words'],state['round']);state['current_word']=word;state['current_scramble']=self.scramble(word);state['used_words'].append(word);state['round_start_time']=now_ts();await self.db.execute('UPDATE game_sessions SET state=? WHERE id=?',(json.dumps(state),int(row['id'])));return self.prompt(state)
    async def timeout(self,group_id:int)->str|None:
        """Resolve an unanswered round and continue the session."""
        row=await self.get_active(group_id)
        if not row:return None
        state=json.loads(row['state']);
        if not state.get('awaiting_answer'):return None
        state['awaiting_answer']=False;await self.db.execute('UPDATE game_sessions SET state=? WHERE id=?',(json.dumps(state),int(row['id'])));prefix=f'☾ No one got it. The word was: {state["current_word"]}.'
        nxt=await self.next_round(group_id);return prefix if not nxt else prefix+'\n\n'+nxt
    async def finish(self,group_id:int)->str|None:
        """Close the game, write history, and return its final leaderboard."""
        row=await self.get_active(group_id)
        if not row:return None
        state=json.loads(row['state']);scores={k:int(v) for k,v in state.get('scores',{}).items()};ordered=sorted(scores.items(),key=lambda x:(-x[1],x[0]));names=[]
        for uid,score in ordered:
            r=await self.db.fetchone('SELECT preferred_name FROM members WHERE user_id=? AND group_id=?',(int(uid),group_id));names.append((str(r[0]) if r and r[0] else uid,score))
        lines=['☾ Word Scramble — Final Scores'];medals=['🥇','🥈','🥉'];lines += [f'{medals[i] if i<3 else "•"} {n} — {s} points' for i,(n,s) in enumerate(names)]
        top=ordered[0][1] if ordered else 0;tied=[n for n,s in names if s==top];lines.append('A tie. Oracle expected nothing less from this group.' if len(tied)>1 else f'{tied[0] if tied else "No one"} wins. Oracle is not surprised. 🌙')
        await self.db.execute('UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=? AND is_active=1',(now_ts(),int(row['id'])));await self.db.execute('INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)',(group_id,self.game_type,int(ordered[0][0]) if ordered and len(tied)==1 else None,json.dumps(scores),now_ts()));return '\n'.join(lines)
    async def endgame(self,group_id:int)->str:
        """End an active scramble immediately and show its partial leaderboard.""";row=await self.get_active(group_id)
        if not row:return '☾ No scramble is active.'
        state=json.loads(row['state']);scores=state.get('scores',{});await self.db.execute('UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=? AND is_active=1',(now_ts(),int(row['id'])));await self.db.execute('INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)',(group_id,self.game_type,None,json.dumps(scores),now_ts()));return '☾ Scramble ended. Partial scores: '+(' · '.join(f'{k}: {v}' for k,v in scores.items()) if scores else 'no points yet.')
