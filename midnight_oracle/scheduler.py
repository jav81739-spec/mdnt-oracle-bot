"""Autonomous morning, evening, 3AM, absence, and rare social events."""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from .config import TIMEZONE,MORNING_HOUR,MORNING_MINUTE,EVENING_HOUR,EVENING_MINUTE,SCHEDULED_MESSAGE_GAP_SECONDS
from .database import Database,now_ts
from .generators.moment_generator import moment
from .engines.absence_engine import AbsenceEngine
from .engines.secret_event_engine import SecretEventEngine

class OracleScheduler:
    """Run quiet, activity-aware scheduled social prompts."""
    def __init__(self,application:Application,db:Database,timezone:ZoneInfo=TIMEZONE)->None:
        """Create the scheduler for one Telegram application."""; self.application=application;self.db=db;self.timezone=timezone;self.scheduler=AsyncIOScheduler(timezone=timezone)
    def start(self)->None:
        """Register autonomous jobs exactly once."""
        if self.scheduler.running:return
        self.scheduler.add_job(self.morning,'cron',hour=MORNING_HOUR,minute=MORNING_MINUTE,id='oracle_morning',replace_existing=True);self.scheduler.add_job(self.evening,'cron',hour=EVENING_HOUR,minute=EVENING_MINUTE,id='oracle_evening',replace_existing=True);self.scheduler.add_job(self.three_am,'cron',hour=3,minute=0,id='oracle_3am',replace_existing=True);self.scheduler.add_job(self.absence_daily,'cron',hour=14,minute=0,id='oracle_absence',replace_existing=True);self.scheduler.add_job(self.secret_daily,'cron',hour=15,minute=0,id='oracle_secret',replace_existing=True);self.scheduler.start()
    async def morning(self)->None:
        """Send morning check-ins only to recently active groups."""
        for r in await self.db.fetchall('SELECT group_id,group_name FROM group_profile WHERE morning_active=1'):
            gid,name=int(r[0]),str(r[1]);
            if await self._gap_ok(gid,'morning') and await self._recent_interaction(gid,3):
                markup=InlineKeyboardMarkup([[InlineKeyboardButton('🌤 Surviving',callback_data='mood:surviving'),InlineKeyboardButton('🙂 Fine',callback_data='mood:fine')],[InlineKeyboardButton('🔥 Ready',callback_data='mood:ready'),InlineKeyboardButton("🥲 Don't ask",callback_data='mood:rough')]]);await self._send(gid,f'Good morning, {name or "the room"}. ☕\nAaj energy kitni hai — honestly?','morning',markup)
    async def evening(self)->None:
        """Send an evening reflection to groups active in the last four hours."""
        for r in await self.db.fetchall('SELECT group_id FROM group_profile WHERE evening_active=1'):
            gid=int(r[0]);
            if await self._gap_ok(gid,'evening') and await self._recent_interaction(gid,0.17):await self._send(gid,'Day khatam. Batao — aaj ka sabse unexpected moment?','evening')
    async def three_am(self)->None:
        """Wake 3AM mode only when the group was active late."""
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            gid=int(r[0]);
            if await self._gap_ok(gid,'3am') and await self._active_late(gid):await self._send(gid,f'☾ {datetime.now(self.timezone).strftime("%H:%M")} — anyone else awake?','3am')
    async def absence_daily(self)->None:
        """Send at most one gentle absence ping per eligible member per day."""
        engine=AbsenceEngine(self.db)
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            gid=int(r[0]);
            for member in await engine.check_group(gid):
                if not await self._group_quiet_for_ping(gid):
                    continue
                try:
                    await self.application.bot.send_message(gid,await engine.generate_ping(member,gid));await engine.record_ping(member)
                except Exception:continue
    async def secret_daily(self)->None:
        """Evaluate one rare privacy-safe secret event per group."""
        engine=SecretEventEngine(self.db)
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            event=await engine.evaluate(int(r[0]))
            if event:
                teaser,reveal=await engine.format_event(event)
                try:await self.application.bot.send_message(event.group_id,teaser,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Reveal 👁',callback_data='secret:'+str(event.group_id))]]));await engine.record(event)
                except Exception:continue
    async def oracle_moment(self,group_id:int)->bool:
        """Send one rare Oracle Moment per day."""
        row=await self.db.fetchone('SELECT sent_at FROM oracle_moments_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1',(group_id,));
        if row and now_ts()-float(row[0])<86400:return False
        text=moment()
        try:await self.application.bot.send_message(group_id,text);await self.db.execute('INSERT INTO oracle_moments_log(group_id,moment_type,content,sent_at) VALUES(?,?,?,?)',(group_id,'organic',text,now_ts()));return True
        except Exception:return False
    async def _send(self,group_id:int,text:str,kind:str,markup:InlineKeyboardMarkup|None=None)->None:
        """Send a scheduled message and persist delivery."""
        try:await self.application.bot.send_message(group_id,text,reply_markup=markup);await self.db.execute('INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)',(group_id,kind,now_ts()))
        except Exception:return
    async def _gap_ok(self,group_id:int,kind:str)->bool:
        """Enforce the four-hour scheduled-message gap.""";r=await self.db.fetchone('SELECT sent_at FROM scheduled_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1',(group_id,));return not r or now_ts()-float(r[0])>=SCHEDULED_MESSAGE_GAP_SECONDS
    async def _recent_interaction(self,group_id:int,days:float)->bool:
        """Check recent member activity.""";r=await self.db.fetchone('SELECT MAX(last_seen) FROM members WHERE group_id=?',(group_id,));return bool(r and float(r[0] or 0)>=now_ts()-days*86400)
    async def _active_late(self,group_id:int)->bool:
        """Check for activity during the preceding three hours.""";return await self._recent_interaction(group_id,0.125)
    async def _group_quiet_for_ping(self,group_id:int)->bool:
        """Require no member activity in the last fifteen minutes before an absence ping.""";r=await self.db.fetchone('SELECT MAX(last_seen) FROM members WHERE group_id=?',(group_id,));return not r or now_ts()-float(r[0] or 0)>900
