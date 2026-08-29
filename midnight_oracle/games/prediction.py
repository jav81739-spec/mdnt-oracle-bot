"""Persistent group predictions and date-based reveals."""
from __future__ import annotations
from datetime import datetime, timezone
from ..database import Database, now_ts

class PredictionEngine:
    """Create and reveal public group predictions without private data."""
    def __init__(self,db:Database)->None:
        """Bind predictions to SQLite."""; self.db=db
    async def create(self,group_id:int,user_id:int,text:str,reveal_at:float)->str:
        """Persist one bounded prediction."""
        text=text.strip()[:500]
        if not text:return '☾ A prediction needs a little substance.'
        await self.db.execute("INSERT INTO predictions(group_id,predictor_user_id,prediction_text,reveal_date,created_at) VALUES(?,?,?,?,?)",(group_id,user_id,text,reveal_at,now_ts())); return '☾ Prediction sealed.'
    async def pending(self,group_id:int)->list[tuple]:
        """Return pending predictions for a group."""
        return await self.db.fetchall("SELECT id,predictor_user_id,prediction_text,reveal_date FROM predictions WHERE group_id=? AND actual_outcome='' ORDER BY reveal_date",(group_id,))
    async def due(self,group_id:int)->list[tuple]:
        """Return predictions whose reveal date has arrived."""
        return await self.db.fetchall("SELECT id,predictor_user_id,prediction_text FROM predictions WHERE group_id=? AND actual_outcome='' AND reveal_date<=? ORDER BY reveal_date",(group_id,now_ts()))
