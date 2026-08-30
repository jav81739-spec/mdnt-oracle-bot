"""Midnight Oracle — Relationship Ritual Engine."""
from __future__ import annotations
import hashlib, time
from datetime import timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from . import social_engine
PREFIX="oracle:rel:"; LOCK_SECONDS=86400

def _state(app): return app.bot_data.setdefault("oracle_relationships", {})
def _pair_key(chat_id,a,b):
    x,y=sorted((int(a),int(b))); return f"{PREFIX}{chat_id}:{x}:{y}"
def _member_from_token(members,token):
    token=token.strip().lstrip("@").lower()
    return next((m for m in members if str(m.get("id"))==token or str(m.get("username","")).lower()==token),None)
async def _targets(update):
    chat,user=update.effective_chat,update.effective_user
    return (chat,user,await social_engine._members(chat.id)) if chat and user else (None,None,None)
def _resolve(update,context,members):
    actor=update.effective_user; msg=update.effective_message
    first=_member_from_token(members,context.args[0]) if context.args else None
    second=_member_from_token(members,context.args[1]) if len(context.args)>1 else None
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        first=first or _member_from_token(members,str(actor.id)); second=second or _member_from_token(members,str(msg.reply_to_message.from_user.id))
    first=first or _member_from_token(members,str(actor.id))
    second=second or (_member_from_token(members,context.args[0]) if len(context.args)==1 else None)
    return (first,second) if first and second and first["id"]!=second["id"] else (None,None)
def _ensure(p):
    for k in ("familiarity","trust","affinity","tension","momentum","attention","chaos","distance","uses"): p.setdefault(k,0)
    return p
def _mention(m): return f"@{m['username']}" if m.get("username") else f"[{m.get('name','someone')}](tg://user?id={m['id']})"
def _score(seed): return 42+(int(hashlib.sha256(seed.encode()).hexdigest(),16)%53)
def _reading(kind,a,b,state):
    pairs=f"{_mention(a)} × {_mention(b)}"
    titles={"thread":"THREAD OPEN","orbit":"ORBIT TRACE","echo":"ECHO FOUND","tether":"TETHER READING","rift":"RIFT READING","spark":"SPARK TRACE","mirror":"MIRROR READING","crossing":"CROSSING","undertow":"UNDERTOW","verdict":"ORACLE VERDICT"}
    bodies={"thread":f"A line keeps appearing between {pairs}. Not loud. Not accidental.","orbit":f"{pairs} keep returning to the same conversational gravity.","echo":f"{pairs} reflect something in each other that neither names directly.","tether":f"{pairs} have a connection that survives ordinary distance.","rift":f"{pairs} carry unfinished tension. Distance is not always the opposite of connection.","spark":f"{pairs} produce unusual attention when their paths cross.","mirror":f"{pairs} keep reflecting opposite sides of the same room.","crossing":f"The paths of {pairs} cross more often than chance would make interesting.","undertow":f"There is a quiet pull beneath {pairs}. The surface is not the whole story.","verdict":f"{pairs}: the connection exists inside the Oracle's records. Its name remains withheld."}
    score=_score(f"{kind}:{a['id']}:{b['id']}:{state.get('uses',0)}")
    return f"☾ *{titles[kind]}*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n{bodies[kind]}\n\n`✦` {_mention(a)}\n`✦` {_mention(b)}\n\n*signal · {score}%*\n\n_The Oracle records patterns. It does not explain them._\n\n🌙 *— Midnight Oracle*"
async def _ritual(kind,update,context):
    chat,_,members=await _targets(update)
    if not chat:return
    a,b=_resolve(update,context,members)
    if not a or not b:
        await update.effective_message.reply_text(f"☾ Use /{kind} @member @member — or reply to a member."); return
    pair=_ensure(_state(context.application).setdefault(_pair_key(chat.id,a["id"],b["id"]),{})); pair["uses"]+=1; pair["last"]=int(time.time())
    deltas={"thread":(2,2,3,0,3,1,0,-1),"orbit":(3,1,2,0,4,3,0,-1),"echo":(4,2,2,0,3,2,0,-1),"tether":(3,4,4,0,2,2,0,-2),"rift":(1,0,0,5,1,1,1,3),"spark":(2,1,5,0,3,4,2,-1),"mirror":(3,3,3,1,2,2,0,0),"crossing":(3,2,3,0,4,3,1,-1),"undertow":(2,2,5,1,3,4,1,-2),"verdict":(2,2,2,0,2,2,0,-1)}[kind]
    for field,delta in zip(("familiarity","trust","affinity","tension","momentum","attention","chaos","distance"),deltas): pair[field]=max(0,min(100,pair[field]+delta))
    await update.effective_message.reply_text(_reading(kind,a,b,pair),parse_mode="Markdown",disable_web_page_preview=True)
async def watch(update,context):
    chat,_,members=await _targets(update)
    if not chat:return
    a,b=_resolve(update,context,members)
    if not a or not b: await update.effective_message.reply_text("☾ Use /watch @member @member — or reply to a member."); return
    p=_ensure(_state(context.application).setdefault(_pair_key(chat.id,a["id"],b["id"]),{})); p["watch"]=True; p["watch_since"]=int(time.time())
    await update.effective_message.reply_text(f"👁️ *WATCH ESTABLISHED*\n\n{_mention(a)} × {_mention(b)}\n\n_The Oracle will keep this thread in its peripheral vision._",parse_mode="Markdown")
async def unwatch(update,context):
    chat,_,members=await _targets(update)
    if not chat:return
    a,b=_resolve(update,context,members)
    if not a or not b: await update.effective_message.reply_text("☾ Use /unwatch @member @member — or reply to a member."); return
    _ensure(_state(context.application).setdefault(_pair_key(chat.id,a["id"],b["id"]),{}))["watch"]=False
    await update.effective_message.reply_text("☾ *WATCH RELEASED*\n\n_The Oracle has stopped actively observing this thread._",parse_mode="Markdown")
async def sealed(update,context):
    chat,_,members=await _targets(update)
    if not chat:return
    a,b=_resolve(update,context,members)
    if not a or not b: await update.effective_message.reply_text("☾ Use /sealed @member @member — or reply to a member."); return
    state=_state(context.application); key=_pair_key(chat.id,a["id"],b["id"])+":sealed"; now=int(time.time()); until=int(state.get(key,0) or 0)
    if until>now:
        hours=timedelta(seconds=until-now).total_seconds()/3600
        await update.effective_message.reply_text(f"🔒 *SEALED*\n\n{_mention(a)} × {_mention(b)}\n\n_This reading is still sealed._\n\n**{hours:.1f} hours remaining**\n\n_The Oracle will not open it early._",parse_mode="Markdown"); return
    state[key]=now+LOCK_SECONDS; p=_ensure(state.setdefault(_pair_key(chat.id,a["id"],b["id"]),{})); p["sealed_at"]=now; p["sealed_until"]=state[key]
    await update.effective_message.reply_text(f"🔒 *THE SEALED HOUR*\n\n{_mention(a)} × {_mention(b)}\n\n_The Oracle found something it refuses to reveal yet._\n\n**24 hours remaining.**\n\n_Do not ask again. The lock is part of the reading._\n\n🌙 *— Midnight Oracle*",parse_mode="Markdown")
COMMANDS={k:k for k in ("thread","orbit","echo","tether","rift","spark","mirror","crossing","undertow","verdict")}
def register(app:Application):
    existing={str(c).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
    for command,kind in COMMANDS.items():
        if command not in existing:
            async def handler(update,context,_kind=kind): await _ritual(_kind,update,context)
            app.add_handler(CommandHandler(command,handler),group=0)
    for name,callback in (("watch",watch),("unwatch",unwatch),("sealed",sealed)):
        if name not in existing: app.add_handler(CommandHandler(name,callback),group=0)
    try:
        from .owner_oracle import register as register_owner
        register_owner(app)
    except Exception:
        import logging; logging.getLogger("midnight.owner").exception("OWNER_SURFACE_REGISTRATION_FAILED")
