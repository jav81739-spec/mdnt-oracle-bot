"""Autonomous scheduler plus durable game and secret-event recovery."""
from __future__ import annotations
import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from .config import TIMEZONE,MORNING_HOUR,MORNING_MINUTE,EVENING_HOUR,EVENING_MINUTE,SCHEDULED_MESSAGE_GAP_SECONDS
from .database import Database,now_ts
from .generators.moment_generator import moment
from .engines.absence_engine import AbsenceEngine
from .engines.secret_event_engine import SecretEventEngine
from .games.would_you_rather import WouldYouRatherGame
from .games.word_scramble import WordScrambleGame

class OracleScheduler:
    """Run scheduled friendship events and recover durable timed workflows."""
    def __init__(self,application:Application,db:Database,timezone:ZoneInfo=TIMEZONE)->None:
        """Create the scheduler.""";self.application=application;self.db=db;self.timezone=timezone;self.scheduler=AsyncIOScheduler(timezone=timezone)
    def start(self)->None:
        """Register autonomous jobs exactly once, including recovery."""
        if self.scheduler.running:return
        self.scheduler.add_job(self.morning,'cron',hour=MORNING_HOUR,minute=MORNING_MINUTE,id='oracle_morning',replace_existing=True);self.scheduler.add_job(self.evening,'cron',hour=EVENING_HOUR,minute=EVENING_MINUTE,id='oracle_evening',replace_existing=True);self.scheduler.add_job(self.three_am,'cron',hour=3,minute=0,id='oracle_3am',replace_existing=True);self.scheduler.add_job(self.absence_daily,'cron',hour=14,minute=0,id='oracle_absence',replace_existing=True);self.scheduler.add_job(self.secret_daily,'cron',hour=15,minute=0,id='oracle_secret',replace_existing=True);self.scheduler.add_job(self.recover_timed,'date',run_date=datetime.now(self.timezone)+timedelta(seconds=2),id='oracle_recovery',replace_existing=True);self.scheduler.start()
    async def recover_timed(self)->None:
        """Recover expired WYR polls, active scramble sessions, and overdue secret events."""
        await SecretEventEngine(self.db).recover_unrevealed(self.application.bot)
        await WouldYouRatherGame(self.db).recover_expired(self.application.bot)
        rows=await self.db.fetchall("SELECT group_id FROM game_sessions WHERE game_type='word_scramble' AND is_active=1")
        for r in rows:
            gid=int(r['group_id']);await self.application.bot.send_message(gid,'☾ Oracle lost its place. Starting fresh.');await self.db.execute("UPDATE game_sessions SET is_active=0,ended_at=? WHERE group_id=? AND game_type='word_scramble' AND is_active=1",(now_ts(),gid))
    async def morning(self)->None:
        """Send morning check-ins only to recently active groups."""
        for r in await self.db.fetchall('SELECT group_id,group_name FROM group_profile WHERE morning_active=1'):
            gid,name=int(r[0]),str(r[1]);
            if await self._gap_ok(gid,'morning') and await self._recent_interaction(gid,3):
                markup=InlineKeyboardMarkup([[InlineKeyboardButton('🌤 Surviving',callback_data='mood:surviving'),InlineKeyboardButton('🙂 Fine',callback_data='mood:fine')],[InlineKeyboardButton('🔥 Ready',callback_data='mood:ready'),InlineKeyboardButton("🥲 Don't ask",callback_data='mood:rough')]]);await self._send(gid,f'Good morning, {name or "the room"}. ☕\nAaj energy kitni hai — honestly?','morning',markup)
    async def evening(self)->None:
        """Send an evening reflection to active groups."""
        for r in await self.db.fetchall('SELECT group_id FROM group_profile WHERE evening_active=1'):
            gid=int(r[0]);
            if await self._gap_ok(gid,'evening') and await self._recent_interaction(gid,.17):await self._send(gid,'Day khatam. Batao — aaj ka sabse unexpected moment?','evening')
    async def three_am(self)->None:
        """Wake 3AM mode only when late activity exists."""
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            gid=int(r[0]);
            if await self._gap_ok(gid,'3am') and await self._active_late(gid):await self._send(gid,f'☾ {datetime.now(self.timezone).strftime("%H:%M")} — anyone else awake?','3am')
    async def absence_daily(self)->None:
        """Send eligible absence pings without interrupting active conversations."""
        engine=AbsenceEngine(self.db)
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            gid=int(r[0]);
            if await self._group_quiet_for_ping(gid):
                for member in await engine.check_group(gid):
                    try:await self.application.bot.send_message(gid,await engine.generate_ping(member,gid));await engine.record_ping(member)
                    except Exception:continue
    async def secret_daily(self)->None:
        """Send a rare secret teaser and schedule its 30-minute reveal."""
        engine=SecretEventEngine(self.db)
        for r in await self.db.fetchall('SELECT group_id FROM group_profile'):
            event=await engine.evaluate(int(r[0]))
            if not event:continue
            teaser,_=await engine.format_event(event)
            try:
                msg=await self.application.bot.send_message(event.group_id,teaser)
                eid=await engine.record(event,msg.message_id)
                await self.application.bot.edit_message_reply_markup(event.group_id,msg.message_id,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Reveal 👁',callback_data=f'reveal_{eid}')]]))
                sent_at=now_ts()
                self.scheduler.add_job(engine.reveal,'date',run_date=datetime.now(self.timezone)+timedelta(minutes=30),args=[eid,self.application.bot,msg.message_id,None,event.group_id],id=f'auto_reveal_{eid}',replace_existing=True)
            except Exception:continue
    async def oracle_moment(self,group_id:int)->bool:
        """Send one rare Oracle Moment per day.""";row=await self.db.fetchone('SELECT sent_at FROM oracle_moments_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1',(group_id,));
        if row and now_ts()-float(row[0])<86400:return False
        text=moment()
        try:await self.application.bot.send_message(group_id,text);await self.db.execute('INSERT INTO oracle_moments_log(group_id,moment_type,content,sent_at) VALUES(?,?,?,?)',(group_id,'organic',text,now_ts()));return True
        except Exception:return False
    async def _send(self,group_id:int,text:str,kind:str,markup:InlineKeyboardMarkup|None=None)->None:
        """Send and log a scheduled message."""
        try:await self.application.bot.send_message(group_id,text,reply_markup=markup);await self.db.execute('INSERT INTO scheduled_log(group_id,schedule_type,sent_at,had_interaction) VALUES(?,?,?,0)',(group_id,kind,now_ts()))
        except Exception:pass
    async def _gap_ok(self,group_id:int,kind:str)->bool:
        """Enforce the scheduled-message gap.""";r=await self.db.fetchone('SELECT sent_at FROM scheduled_log WHERE group_id=? ORDER BY sent_at DESC LIMIT 1',(group_id,));return not r or now_ts()-float(r[0])>=SCHEDULED_MESSAGE_GAP_SECONDS
    async def _recent_interaction(self,group_id:int,days:float)->bool:
        """Check recent member activity.""";r=await self.db.fetchone('SELECT MAX(last_seen) FROM members WHERE group_id=?',(group_id,));return bool(r and float(r[0] or 0)>=now_ts()-days*86400)
    async def _active_late(self,group_id:int)->bool:
        """Check recent activity for 3AM mode.""";return await self._recent_interaction(group_id,.125)
    async def _group_quiet_for_ping(self,group_id:int)->bool:
        """Require a quiet group before an absence ping.""";r=await self.db.fetchone('SELECT MAX(last_seen) FROM members WHERE group_id=?',(group_id,));return not r or now_ts()-float(r[0] or 0)>900
