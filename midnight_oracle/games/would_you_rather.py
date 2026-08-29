"""Complete Telegram-native Would You Rather poll lifecycle."""
from __future__ import annotations
import json
from openai import AsyncOpenAI
from telegram import Message
from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..database import Database, now_ts

class WouldYouRatherGame:
    """Create, track, close, and recover 60-second WYR polls."""
    game_type='would_you_rather'
    def __init__(self,db:Database)->None:
        """Bind the game to SQLite.""";self.db=db;self.client=AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    async def _dilemma(self)->tuple[str,str]:
        """Generate two safe dilemma options, with a local pair if AI is unavailable."""
        if self.client:
            try:
                r=await self.client.chat.completions.create(model=OPENAI_MODEL,messages=[{'role':'system','content':'Generate one fun, safe Would You Rather dilemma. Return exactly two lines: A: ... and B: ... . No preamble.'}],temperature=.9,max_tokens=60)
                lines=[x.strip() for x in (r.choices[0].message.content or '').splitlines() if x.strip()]
                if len(lines)>=2:return lines[0].split(':',1)[-1].strip(),lines[1].split(':',1)[-1].strip()
            except Exception:pass
        return 'Always know the time','Always know what people are thinking'
    async def start_poll(self,chat_id:int,bot,starter_id:int)->Message:
        """Send and persist a native non-anonymous 60-second poll."""
        if await self.db.get_active_wyr_session(chat_id):raise RuntimeError('A WYR poll is already active')
        a,b=await self._dilemma();msg=await bot.send_poll(chat_id,f'☾ Would you rather…\nA: {a}\nB: {b}',[a,b],is_anonymous=False,allows_multiple_answers=False,open_period=60)
        state={'poll_id':msg.poll.id,'message_id':msg.message_id,'option_a':a,'option_b':b,'voters_a':[],'voters_b':[],'group_id':chat_id,'started_at':now_ts()}
        await self.db.execute("INSERT INTO game_sessions(group_id,game_type,state,current_turn_user_id,started_at,is_active) VALUES(?,?,?,?,?,1)",(chat_id,self.game_type,json.dumps(state),starter_id,now_ts()));return msg
    async def handle_poll_answer(self,poll_id:str,user_id:int,option:int)->bool:
        """Silently record a user's first WYR vote.""";return await self.db.update_wyr_votes(poll_id,user_id,option)
    async def close_poll(self,poll_id:str,bot,chat_id:int)->bool:
        """Finalize one active poll, comment in the group, and record history."""
        rows=await self.db.fetchall("SELECT id,state FROM game_sessions WHERE game_type='would_you_rather' AND is_active=1")
        target=None
        for row in rows:
            state=json.loads(row['state'])
            if str(state.get('poll_id'))==str(poll_id):target=(int(row['id']),state);break
        if not target:return False
        sid,state=target;a=state.get('voters_a',[]);b=state.get('voters_b',[]);ca,cb=len(a),len(b)
        if not ca and not cb:comment='☾ The group has chosen silence. Noted.'
        elif ca==cb:comment=f'☾ A perfect split — {ca} on each side. Oracle expected nothing less.'
        else:comment=await self._comment(state,a,b,chat_id,ca,cb)
        result={'poll_id':poll_id,'option_a':state.get('option_a'),'option_b':state.get('option_b'),'count_a':ca,'count_b':cb,'winner_side':'tie' if ca==cb else ('a' if ca>cb else 'b')}
        if not await self._close_atomic(sid,result):return False
        try:await bot.stop_poll(chat_id,int(state['message_id']))
        except Exception:pass
        try:await bot.send_message(chat_id,comment)
        except Exception:pass
        return True
    async def _comment(self,state:dict,a:list,b:list,chat_id:int,ca:int,cb:int)->str:
        """Generate the short Oracle poll-result comment."""
        names=[]
        for uid in a+b:
            r=await self.db.fetchone('SELECT preferred_name FROM members WHERE user_id=? AND group_id=?',(int(uid),chat_id));names.append(str(r[0]) if r and r[0] else 'someone')
        prompt=f'''You are Midnight Oracle. A 60-second group vote just finished.\nDilemma: "{state.get("option_a")}" vs "{state.get("option_b")}"\nVoted for A: {", ".join(names[:ca])} ({ca} people)\nVoted for B: {", ".join(names[ca:ca+cb])} ({cb} people)\nWrite ONE comment (1–2 lines max). Warm, slightly witty. Optionally call out an interesting split or name a member naturally. Do not start with "I". Oracle voice: calm, warm, restrained.'''
        if self.client:
            try:
                r=await self.client.chat.completions.create(model=OPENAI_MODEL,messages=[{'role':'system','content':prompt}],temperature=.75,max_tokens=70);text=(r.choices[0].message.content or '').strip();
                if text:return text[:400]
            except Exception:pass
        return '☾ The room has spoken. Interesting.'
    async def _close_atomic(self,sid:int,result:dict)->bool:
        """Atomically close a WYR session and record its result."""
        await self.db.db.execute('BEGIN IMMEDIATE')
        try:
            cur=await self.db.db.execute('UPDATE game_sessions SET is_active=0,ended_at=? WHERE id=? AND is_active=1',(now_ts(),sid))
            if cur.rowcount!=1:await self.db.db.rollback();return False
            r=await self.db.db.execute('SELECT group_id FROM game_sessions WHERE id=?',(sid,));row=await r.fetchone();await self.db.db.execute('INSERT INTO game_history(group_id,game_type,winner_user_id,summary,played_at) VALUES(?,?,?,?,?)',(int(row[0]),self.game_type,None,json.dumps(result),now_ts()));await self.db.db.commit();return True
        except Exception:await self.db.db.rollback();raise
    async def recover_expired(self,bot)->None:
        """Close active WYR sessions whose 60 seconds elapsed during downtime."""
        rows=await self.db.fetchall("SELECT state FROM game_sessions WHERE game_type='would_you_rather' AND is_active=1")
        for row in rows:
            state=json.loads(row['state']);
            if now_ts()-float(state.get('started_at',now_ts()))>=60:await self.close_poll(str(state.get('poll_id')),bot,int(state.get('group_id')))
