"""Crash-safe time capsules backed by the shared durable store."""
from __future__ import annotations

import datetime
import uuid

from telegram import Update
from telegram.ext import ContextTypes, Application
from handlers import storage

STORAGE_KEY = "timecapsules:v2"


def _parse_duration(value: str):
    if len(value) < 2: return None
    try: amount = int(value[:-1])
    except ValueError: return None
    multiplier = {"m":60,"h":3600,"d":86400}.get(value[-1].lower())
    return amount * multiplier if multiplier and amount > 0 else None

async def _load():
    value = await storage.load(STORAGE_KEY, {})
    return value if isinstance(value,dict) else {}

async def _save(value):
    if not await storage.save(STORAGE_KEY,value): raise RuntimeError("time capsule state could not be persisted")

async def _fire_capsule(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    capsule = job.data
    chat_id = str(job.chat_id)
    marker = f"timecapsule:delivered:{capsule['id']}"
    async with storage.lock(f"timecapsule-fire:{capsule['id']}", ttl=30, wait=0.5) as acquired:
        if not acquired or await storage.exists(marker): return
        if not await storage.setnx(marker, "1", 86400): return
        try:
            await context.bot.send_message(int(chat_id), f"⏳ *A time capsule has unlocked!*\n\nSealed by {capsule['author']}:\n\n\"{capsule['text']}\"", parse_mode="Markdown")
        except Exception:
            await storage.delete(marker)
            raise
        async with storage.lock("timecapsules-state") as state_lock:
            if not state_lock: return
            capsules = await _load(); pending = capsules.get(chat_id, [])
            capsules[chat_id] = [c for c in pending if c.get("id") != capsule.get("id")]
            if not capsules[chat_id]: capsules.pop(chat_id,None)
            await _save(capsules)

async def timecapsule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /timecapsule [delay] [message]\nDelay examples: 10m, 2h, 3d"); return
    delay = _parse_duration(context.args[0])
    if delay is None or delay > 365 * 86400:
        await update.message.reply_text("Invalid delay. Use a positive duration such as 10m, 2h, or 3d (max 365d)."); return
    chat_id = str(update.effective_chat.id); author = update.effective_user
    unlock_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay)
    capsule = {"id":f"{author.id}-{uuid.uuid4().hex}","text":" ".join(context.args[1:])[:4000],"author":author.first_name[:80],"unlock_at":unlock_at.isoformat()}
    async with storage.lock("timecapsules-state") as acquired:
        if not acquired: await update.message.reply_text("⏳ Capsule storage is busy — try again."); return
        capsules=await _load(); capsules.setdefault(chat_id,[]).append(capsule); await _save(capsules)
    context.job_queue.run_once(_fire_capsule, when=delay, data=capsule, chat_id=int(chat_id), name=f"capsule:{capsule['id']}")
    await update.message.reply_text(f"🔒 Time capsule sealed! It'll unlock in {context.args[0]}.",parse_mode="Markdown")

async def list_capsules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending=(await _load()).get(str(update.effective_chat.id),[])
    if not pending: await update.message.reply_text("No time capsules sealed yet — use /timecapsule to start one."); return
    lines=[f"🔒 by {c['author']}, unlocking at {c['unlock_at'][:16].replace('T',' ')} UTC" for c in pending]
    await update.message.reply_text("📦 *Sealed capsules (pending):*\n\n"+"\n".join(lines),parse_mode="Markdown")

async def load_and_reschedule(app: Application):
    capsules=await _load(); now=datetime.datetime.now(datetime.timezone.utc); resumed=expired=0
    for chat_id,pending in list(capsules.items()):
        for capsule in list(pending):
            try: unlock_at=datetime.datetime.fromisoformat(capsule["unlock_at"])
            except (KeyError,ValueError,TypeError): continue
            remaining=(unlock_at-now).total_seconds(); app.job_queue.run_once(_fire_capsule,when=max(1,remaining),data=capsule,chat_id=int(chat_id),name=f"capsule:{capsule['id']}")
            if remaining<=0: expired+=1
            else: resumed+=1
    if resumed or expired:
        import logging
        logging.getLogger(__name__).info("Time capsules: resumed %d, scheduled %d overdue",resumed,expired)
