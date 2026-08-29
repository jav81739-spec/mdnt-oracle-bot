"""Autonomous morning, evening, and adaptive 3AM events."""
from __future__ import annotations
from datetime import datetime, time
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .config import TIMEZONE, MORNING_HOUR, MORNING_MINUTE, EVENING_HOUR, EVENING_MINUTE, SCHEDULED_MESSAGE_GAP_SECONDS, THREE_AM_START, THREE_AM_END
from .database import Database, now_ts
from .generators.moment_generator import moment


class OracleScheduler:
    """Run quiet, activity-aware scheduled social prompts."""

    def __init__(self, application: Application, db: Database, timezone: ZoneInfo = TIMEZONE) -> None:
        """Create the scheduler for one Telegram application."""
        self.application = application
        self.db = db
        self.timezone = timezone
        self.scheduler = AsyncIOScheduler(timezone=timezone)

    def start(self) -> None:
        """Register all autonomous jobs and start the scheduler once."""
        if self.scheduler.running:
            return
        self.scheduler.add_job(self.morning, "cron", hour=MORNING_HOUR, minute=MORNING_MINUTE, id="oracle_morning", replace_existing=True)
        self.scheduler.add_job(self.evening, "cron", hour=EVENING_HOUR, minute=EVENING_MINUTE, id="oracle_evening", replace_existing=True)
        self.scheduler.add_job(self.three_am, "cron", hour=THREE_AM_END, minute=0, id="oracle_3am", replace_existing=True)
        self.scheduler.start()

    async def morning(self) -> None:
        """Send a morning check-in only to groups with recent engagement history."""
        rows = await self.db.fetchall("SELECT group_id,group_name,morning_active FROM group_profile WHERE morning_active=1")
        for row in rows:
            gid, name = int(row[0]), str(row[1])
            if not await self._gap_ok(gid, "morning") or not await self._recent_interaction(gid, 3):
                continue
            text = f"Good morning, {name or 'baithak'}. ☕\nAaj energy kitni hai — honestly?"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🌤 Surviving", callback_data="mood:surviving"), InlineKeyboardButton("🙂 Fine", callback_data="mood:fine")], [InlineKeyboardButton("🔥 Ready", callback_data="mood:ready"), InlineKeyboardButton("🥲 Don't ask", callback_data="mood:rough")]])
            await self._send(gid, text, "morning", markup)

    async def evening(self) -> None:
        """Send an evening reflection only when the group was active recently."""
        rows = await self.db.fetchall("SELECT group_id FROM group_profile WHERE evening_active=1")
        for row in rows:
            gid = int(row[0])
            if await self._gap_ok(gid, "evening") and await self._recent_interaction(gid, 4):
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("😌 peaceful", callback_data="mood:peaceful"), InlineKeyboardButton("😂 chaotic", callback_data="mood:chaotic")], [InlineKeyboardButton("🥲 rough", callback_data="mood:rough"), InlineKeyboardButton("🤐 private", callback_data="mood:private")]])
                await self._send(gid, "Day khatam. Batao — aaj ka sabse unexpected moment?", "evening", markup)

    async def three_am(self) -> None:
        """Wake the 3AM mode only for groups that were genuinely active after midnight."""
        rows = await self.db.fetchall("SELECT group_id FROM group_profile")
        for row in rows:
            gid = int(row[0])
            if await self._gap_ok(gid, "3am") and await self._active_late(gid):
                await self._send(gid, f"☾ {datetime.now(self.timezone).strftime('%H:%M')} — anyone else awake?", "3am")

    async def oracle_moment(self, group_id: int) -> bool:
        """Attempt one rare Oracle Moment per group per day."""
        row = await self.db.fetchone("SELECT sent_at FROM oracle_moments_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1", (group_id,))
        if row and now_ts() - float(row[0]) < 86400:
            return False
        text = moment()
        try:
            await self.application.bot.send_message(group_id, text)
            await self.db.execute("INSERT INTO oracle_moments_log(group_id,moment_type,content,sent_at) VALUES(?,?,?,?)", (group_id, "organic", text, now_ts()))
            return True
        except Exception:
            return False

    async def _send(self, group_id: int, text: str, kind: str, markup: InlineKeyboardMarkup | None = None) -> None:
        """Send a scheduled message and persist its delivery timestamp."""
        try:
            await self.application.bot.send_message(group_id, text, reply_markup=markup)
            await self.db.execute("INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)", (group_id, kind, now_ts()))
        except Exception:
            return

    async def _gap_ok(self, group_id: int, kind: str) -> bool:
        """Enforce the global scheduled-message gap."""
        row = await self.db.fetchone("SELECT sent_at FROM scheduled_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1", (group_id,))
        return not row or now_ts() - float(row[0]) >= SCHEDULED_MESSAGE_GAP_SECONDS

    async def _recent_interaction(self, group_id: int, days: int) -> bool:
        """Check whether the group has meaningful member activity in a recent window."""
        row = await self.db.fetchone("SELECT MAX(last_seen) FROM members WHERE group_id=?", (group_id,))
        return bool(row and float(row[0] or 0) >= now_ts() - days * 86400)

    async def _active_late(self, group_id: int) -> bool:
        """Check for recent activity during the late-night window."""
        cutoff = now_ts() - 3 * 3600
        row = await self.db.fetchone("SELECT MAX(last_seen) FROM members WHERE group_id=?", (group_id,))
        return bool(row and float(row[0] or 0) >= cutoff)
