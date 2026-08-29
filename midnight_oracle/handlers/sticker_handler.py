"""Contextual Telegram reactions and stickers with persistent rate limits."""
from __future__ import annotations
from dataclasses import dataclass
from ..database import Database, now_ts
from ..data.sticker_map import STICKER_CONTEXTS

@dataclass(slots=True)
class StickerDecision:
    """Describe whether a contextual media action should be sent."""
    should_send:bool; sticker_id:str|None; reaction_emoji:str|None

class StickerHandler:
    """Choose restrained media responses and persist group media limits."""
    def __init__(self,db:Database)->None:
        """Bind the handler to SQLite."""; self.db=db
    async def evaluate(self,message:object,mood:object,context:object)->StickerDecision:
        """Evaluate one message without sending or raising."""
        try:
            text=str(getattr(message,'text',None) or '').lower(); stress=float(getattr(mood,'stress',0)); humour=float(getattr(mood,'humour',0)); late=bool(getattr(context,'is_late_night',False))
            rows=await self.db.fetchall("SELECT COUNT(*) FROM sticker_events WHERE group_id=? AND sent_at>?",(int(context.group_id),now_ts()-3600))
            if int(rows[0][0])>=3:return StickerDecision(False,None,None)
            if text and any(x in text for x in ('ho gaya','finally','cleared','yesss')): key='win_celebration'
            elif stress>.8 and any(x in text for x in ('thak','tired','exhausted','neend')): key='deep_exhaustion'
            elif humour>.75 and any(x in text for x in ('haha','lol','😂','💀')): key='something_ridiculous'
            elif late and not text:key='late_night_quiet'
            else:return StickerDecision(False,None,None)
            item=STICKER_CONTEXTS[key]; return StickerDecision(bool(item['sticker_id']),item['sticker_id'],None if item['sticker_id'] else item['emoji'])
        except Exception:return StickerDecision(False,None,None)
    async def record(self,group_id:int,context_name:str,sticker_id:str|None)->None:
        """Persist one media event."""
        await self.db.execute("INSERT INTO sticker_events(group_id,trigger_context,sticker_id,sent_at) VALUES(?,?,?,?)",(group_id,context_name,sticker_id,now_ts()))
