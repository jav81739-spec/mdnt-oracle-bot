"""Inside-joke detection and safe callback generation."""
from __future__ import annotations
import random, re
from ..database import Database, now_ts

class JokeEngine:
    """Learn recurring, non-sensitive group references and occasionally callback to them."""
    def __init__(self, db: Database) -> None:
        """Bind the engine to persistent storage."""
        self.db = db

    @staticmethod
    def _key(text: str) -> str:
        """Normalize a message into a compact phrase candidate."""
        words = re.findall(r"[\w']+", text.lower())
        return " ".join(words[:12])[:160]

    async def observe(self, message: str, sender_id: int, group_id: int) -> None:
        """Silently count repeated phrase candidates across members and days."""
        key = self._key(message)
        if len(key.split()) < 2 or len(key) > 160:
            return
        if any(x in key for x in ("suicide", "self harm", "kill myself", "die", "abuse")):
            return
        day = int(now_ts() // 86400)
        row = await self.db.fetchone("SELECT id,members_involved FROM inside_jokes WHERE group_id=? AND joke_text=?", (group_id, key))
        if row:
            members = {int(x) for x in str(row[1] or "").split(",") if x.isdigit()}
            members.add(sender_id)
            await self.db.execute("UPDATE inside_jokes SET last_referenced=?,reference_count=reference_count+1,members_involved=? WHERE id=?", (now_ts(), ",".join(map(str, members)), int(row[0])))
        else:
            await self.db.execute("INSERT INTO inside_jokes(group_id,joke_text,origin_message,first_seen,last_referenced,reference_count,members_involved,first_day) VALUES(?,?,?,?,?,?,?,?)", (group_id,key,message[:500],now_ts(),now_ts(),1,str(sender_id),day))
        await self.db.execute("DELETE FROM inside_jokes WHERE id IN (SELECT id FROM inside_jokes WHERE group_id=? ORDER BY last_referenced DESC LIMIT -1 OFFSET 20)", (group_id,))

    async def detect_callback_opportunity(self, message: str, group_id: int) -> str | None:
        """Return a probability-gated callback when a mature joke matches."""
        key = self._key(message)
        rows = await self.db.fetchall("SELECT joke_text,reference_count,members_involved,first_day,last_referenced FROM inside_jokes WHERE group_id=? AND reference_count>=3 ORDER BY last_referenced DESC LIMIT 20", (group_id,))
        today = int(now_ts() // 86400)
        for row in rows:
            if today - int(row[3]) < 1 or len(str(row[2] or "").split(",")) < 2:
                continue
            phrase = str(row[0])
            if phrase in key or key in phrase:
                if random.random() > 0.15:
                    return None
                return random.choice((f"Ah. {phrase} energy detected. ☾", f"Some things never change. {phrase} lives on.", f"Don't worry, I'm not going to mention the legendary {phrase}. 😂"))
        return None

    async def get_random_callback(self, group_id: int) -> str | None:
        """Return a mature joke callback no more than once per 48 hours per joke."""
        cutoff = now_ts() - 172800
        rows = await self.db.fetchall("SELECT id,joke_text,last_referenced FROM inside_jokes WHERE group_id=? AND reference_count>=3 AND last_referenced<? ORDER BY RANDOM() LIMIT 1", (group_id, cutoff))
        if not rows:
            return None
        row = rows[0]
        await self.db.execute("UPDATE inside_jokes SET last_referenced=? WHERE id=?", (now_ts(), int(row[0])))
        return f"Some things never change. {row[1]} lives on. ☾"
