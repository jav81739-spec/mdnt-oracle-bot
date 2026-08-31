"""Midnight Oracle — private relationship ritual surface."""
from __future__ import annotations
import hashlib
import random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from . import social_engine
from core.oracle_instinct import choose_pair

PREFIX="oracle:rel:"; ORACLE_HOUR=0; ORACLE_MINUTE=7

def _state(app): return app.bot_data.setdefault("oracle_relationships", {})
def _pair_key(chat_id,a,b):
    x,y=sorted((int(a),int(b))); return f"{PREFIX}{chat_id}:{x}:{y}"
def _member_from_token(members,token):
    token=token.strip().lstrip("@").casefold()
    return next((m for m in members if str(m.get("username","")).casefold()==token),None)
def _display(m):
    username=str(m.get("username","")).strip(); return f"@{username}" if username else str(m.get("name","someone")).strip() or "someone"
def _pair_display(a,b): return f"{_display(a)} × {_display(b)}"
async def _targets(update):
    chat,user=update.effective_chat,update.effective_user
    return (chat,user,await social_engine._members(chat.id)) if chat and user else (None,None,[])

def _resolve(update,context,members,kind="bond"):
    """Honor explicit targets; otherwise Oracle Instinct chooses the pair."""
    actor=update.effective_user; msg=update.effective_message
    first=_member_from_token(members,context.args[0]) if context.args else None
    second=_member_from_token(members,context.args[1]) if len(context.args)>1 else None
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        rid=msg.reply_to_message.from_user.id
        second=second or next((m for m in members if int(m.get("id",-1))==rid),None)
        if not first and actor: first=next((m for m in members if int(m.get("id",-1))==actor.id),None)
    if not first and actor: first=next((m for m in members if int(m.get("id",-1))==actor.id),None)
    if not second and len(context.args)==1: second=_member_from_token(members,context.args[0])
    if first and second and first["id"]!=second["id"]: return first,second
    if not context.args and not (msg and msg.reply_to_message) and len(members)>=2:
        return choose_pair(context.application,update.effective_chat.id,members,kind) or (None,None)
    return (None,None)

def _ensure(p):
    for k in ("familiarity","trust","affinity","tension","momentum","attention","chaos","distance","uses"): p.setdefault(k,0)
    return p

def _score(seed): return 42+(int(hashlib.sha256(seed.encode()).hexdigest(),16)%53)

def _reading(kind,a,b,state):
    pairs=_pair_display(a,b)
    titles={"bond":"BOND READING","thread":"THE WEAVE","orbit":"ORBIT TRACE","echo":"ECHO FOUND","tether":"THE ANCHOR","rift":"THE FRACTURE","spark":"EMBER TRACE","mirror":"MIRROR READING","crossing":"CROSSING","undertow":"UNDERTOW","verdict":"ORACLE EDICT"}
    bodies={"bond":f"The Oracle chose {pairs} without being asked. Something between these two keeps drawing its attention.","thread":f"A line keeps appearing between {pairs}. Not loud. Not accidental.","orbit":f"{pairs} keep returning to the same conversational gravity.","echo":f"{pairs} reflect something in each other that neither names directly.","tether":f"{pairs} have a connection that survives ordinary distance.","rift":f"{pairs} carry unfinished tension. Distance is not always the opposite of connection.","spark":f"{pairs} produce unusual attention when their paths cross.","mirror":f"{pairs} keep reflecting opposite sides of the same room.","crossing":f"The paths of {pairs} cross often enough for the Oracle to notice.","undertow":f"There is a quiet pull beneath {pairs}. The surface is not the whole story.","verdict":f"{pairs}: the connection exists inside the Oracle's records. Its name remains withheld."}
    score=_score(f"{kind}:{a['id']}:{b['id']}:{state.get('uses',0)}")
    return f"☾ *{titles[kind]}*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{bodies[kind]}\n\n✦ {_display(a)}\n✦ {_display(b)}\n\n*signal · {score}%*\n\n_The Oracle records patterns. It does not explain them._\n\n🌙 *— Midnight Oracle*"

async def _ritual(kind,update,context):
    chat,_,members=await _targets(update)
    if not chat:return
    if len(members)<2:
        await update.effective_message.reply_text("☾ I need at least two known group members before I can choose the pair.")
        return
    a,b=_resolve(update,context,members,kind)
    if not a or not b:
        await update.effective_message.reply_text(f"☾ Use /{kind} with no arguments and let the Oracle choose — or reply to a member.")
        return
    pair=_ensure(_state(context.application).setdefault(_pair_key(chat.id,a["id"],b["id"]),{})); pair["uses"]+=1; pair["last"]=int(datetime.now(timezone.utc).timestamp())
    deltas={"bond":(4,3,5,0,4,3,1,-1),"thread":(2,2,3,0,3,1,0,-1),"orbit":(3,1,2,0,4,3,0,-1),"echo":(4,2,2,0,3,2,0,-1),"tether":(3,4,4,0,2,2,0,-2),"rift":(1,0,0,5,1,1,1,3),"spark":(2,1,5,0,3,4,2,-1),"mirror":(3,3,3,1,2,2,0,0),"crossing":(3,2,3,0,4,3,1,-1),"undertow":(2,2,5,1,3,4,1,-2),"verdict":(2,2,2,0,2,2,0,-1)}[kind]
    for field,delta in zip(("familiarity","trust","affinity","tension","momentum","attention","chaos","distance"),deltas): pair[field]=max(0,min(100,pair[field]+delta))
    await update.effective_message.reply_text(_reading(kind,a,b,pair),parse_mode="Markdown",disable_web_page_preview=True)

async def watch(update,context): await _watch_change(update,context,True)
async def unwatch(update,context): await _watch_change(update,context,False)
async def _watch_change(update,context,enabled):
    chat,_,members=await _targets(update); a,b=_resolve(update,context,members,"bond") if chat else (None,None)
    if not chat:return
    if not a or not b: await update.effective_message.reply_text("☾ Use /gaze with no arguments and let the Oracle choose — or reply to a member.");return
    p=_ensure(_state(context.application).setdefault(_pair_key(chat.id,a["id"],b["id"]),{})); p["watch"]=bool(enabled)
    if enabled:p["watch_since"]=int(datetime.now(timezone.utc).timestamp())
    await update.effective_message.reply_text(f"👁️ *GAZE ESTABLISHED*\n\n{_pair_display(a,b)}\n\n_The Oracle keeps this thread in its peripheral vision._" if enabled else "☾ *GAZE RELEASED*\n\n_The Oracle has stepped away from this thread._",parse_mode="Markdown")

def _cycle(now):
    local=now.astimezone(social_engine.ORACLE_TZ); boundary=local.replace(hour=ORACLE_HOUR,minute=ORACLE_MINUTE,second=0,microsecond=0); start=boundary-timedelta(days=1) if local<boundary else boundary; return start,start+timedelta(days=1)

async def sealed(update,context):
    chat,_,members=await _targets(update); a,b=_resolve(update,context,members,"bond") if chat else (None,None)
    if not chat:return
    if not a or not b: await update.effective_message.reply_text("☾ Use /veil with no arguments and let the Oracle choose — or reply to a member.");return
    now=datetime.now(timezone.utc); start,end=_cycle(now); key=_pair_key(chat.id,a["id"],b["id"]); lock_key=f"{key}:veil:{start.date().isoformat()}"; stored=await social_engine._get(lock_key)
    if not stored and now>=start.astimezone(timezone.utc): await social_engine._set(lock_key,str(int(end.timestamp())),ttl=172800); stored=str(int(end.timestamp()))
    until=int(stored) if stored else int(end.timestamp()); remaining=max(0,until-int(now.timestamp())); hours,rem=divmod(remaining,3600); minutes,seconds=divmod(rem,60)
    if not stored:
        text=f"🔒 *THE VEIL IS SLEEPING*\n\n{_pair_display(a,b)}\n\n_The next seal opens at exactly **00:07 IST**._\n\n**{hours:02d}h {minutes:02d}m {seconds:02d}s until the hour.**\n\n_The Oracle does not move the hour._"
    elif remaining<=0:text="☾ *THE VEIL HAS OPENED.*\n\n_The sealed hour has passed. The Oracle may reveal what was withheld._"
    else:text=f"🔒 *THE VEIL IS DRAWN*\n\n{_pair_display(a,b)}\n\n_This reading is sealed until the next **00:07 IST**._\n\n**{hours:02d}h {minutes:02d}m {seconds:02d}s remaining**\n\n_The lock cannot be moved, refreshed, or opened early._\n\n🌙 *— Midnight Oracle*"
    await update.effective_message.reply_text(text,parse_mode="Markdown",disable_web_page_preview=True)

COMMANDS={"bond":"bond","weave":"thread","orbit":"orbit","echo":"echo","anchor":"tether","fracture":"rift","ember":"spark","mirror":"mirror","crossing":"crossing","undertow":"undertow","edict":"verdict"}
ALIASES={"thread":"thread","tether":"tether","rift":"rift","spark":"spark","verdict":"verdict"}

def register(app:Application):
    existing={str(c).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
    for command,kind in {**COMMANDS,**ALIASES}.items():
        if command in existing:continue
        async def handler(update,context,_kind=kind): await _ritual(_kind,update,context)
        app.add_handler(CommandHandler(command,handler),group=0)
    for command,callback in (("watch",watch),("unwatch",unwatch),("sealed",sealed),("gaze",watch),("release",unwatch),("veil",sealed)):
        if command not in existing:app.add_handler(CommandHandler(command,callback),group=0)
    try:
        from .owner_oracle import register as register_owner; register_owner(app)
    except Exception:
        import logging; logging.getLogger("midnight.owner").exception("OWNER_SURFACE_REGISTRATION_FAILED")
