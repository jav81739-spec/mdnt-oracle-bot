"""Safe, warm roast generation for established members."""
from __future__ import annotations
import random
from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..database import Database
from openai import AsyncOpenAI

class RoastGenerator:
    """Generate dignity-preserving roasts only for invited, established members."""
    def __init__(self,db:Database|None=None)->None:
        """Create the generator with optional persistence."""; self.db=db
    async def generate(self,target:object,trigger_message:str,group_context:object)->str:
        """Generate one safe roast, using GPT-4o when configured and a local fallback otherwise."""
        tier=str(getattr(target,'relationship_tier','new')); name=str(getattr(target,'preferred_name','friend')); mood=str(getattr(group_context,'mood_summary','casual'))
        if tier not in {'known','close'}: return '☾ Nice try. I know better than to roast you yet.'
        blocked=('weight','looks','appearance','mental health','family','money','finance','suicide','self harm')
        if any(x in trigger_message.lower() for x in blocked): return '☾ That one stays out of the joke.'
        if OPENAI_API_KEY:
            try:
                client=AsyncOpenAI(api_key=OPENAI_API_KEY)
                r=await client.chat.completions.create(model=OPENAI_MODEL,messages=[{'role':'system','content':'You are Midnight Oracle, calm witty deadpan. Write one warm roast, max 2 lines. Never mention appearance, weight, mental health, family, money, or genuine worries. Preserve dignity. Hinglish naturally when appropriate.'},{'role':'user','content':f'Member: {name} ({tier})\nMessage: {trigger_message}\nGroup vibe: {mood}'}],temperature=.8,max_tokens=70)
                text=(r.choices[0].message.content or '').strip(); return text[:300] if text else '☾ You walked into that one yourself.'
            except Exception: pass
        return random.choice((f"{name}, tumne khud setup kiya tha… Oracle ne bas notice kiya. ☾",f"Bold strategy, {name}. Execution thodi… artistic thi.","☾ That was almost a plan. Almost."))
