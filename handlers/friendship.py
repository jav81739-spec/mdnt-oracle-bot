"""Social relationship commands with Oracle-selected members."""
from __future__ import annotations
import random
from typing import Any
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention
from core.oracle_instinct import choose_one, choose_pair

bestie_pairs: dict[int, Any] = {}
declared_besties: dict[int, dict[int, Any]] = {}
message_counts: dict[int, dict[int, dict[str, Any]]] = {}
DUO_PREFIXES = ["Chaos", "Dream", "Menace", "Golden", "Rogue"]
DUO_SUFFIXES = ["Duo", "Squad", "Twins", "Crew"]
SHIP_VERDICTS = {"low":["chaotic and doomed 💀","friends at best, enemies at worst 😭"],"mid":["could work with effort 🤞","50/50, coin flip energy"],"high":["written in the stars ✨","unreasonably perfect together"]}

def _ship_name(a: str, b: str) -> str:
    return (a[:max(1,len(a)//2)] + b[len(b)//2:]).title()

def _members(chat_id: int) -> list[dict[str, Any]]:
    return [{"id":int(uid),"name":str(d.get("name") or "someone"),"activity_score":min(1.0,max(0.0,float(d.get("count",0))/20.0)),"is_bot":bool(d.get("is_bot",False))} for uid,d in message_counts.get(chat_id,{}).items() if isinstance(d,dict) and uid]

def _member_from_user(user) -> dict[str, Any]:
    return {"id":int(user.id),"name":user.first_name or "someone","activity_score":0.5,"is_bot":bool(user.is_bot)}

async def _pair(update, context, kind):
    message,chat=update.effective_message,update.effective_chat
    if not message or not chat:return None
    if message.reply_to_message and message.reply_to_message.from_user:
        actor,target=update.effective_user,message.reply_to_message.from_user
        if actor and actor.id != target.id:return _member_from_user(actor),_member_from_user(target)
    return choose_pair(context.application,chat.id,_members(chat.id),kind=kind)

async def _single_target(update, context, kind, allow_self=False):
    message,chat,actor=update.effective_message,update.effective_chat,update.effective_user
    if not message or not chat:return None
    if message.reply_to_message and message.reply_to_message.from_user:
        target=message.reply_to_message.from_user
        if allow_self or not actor or target.id != actor.id:return _member_from_user(target)
    members=_members(chat.id)
    if not allow_self and actor:members=[m for m in members if m["id"] != actor.id]
    return choose_one(context.application,chat.id,members,kind=kind)

async def ship(update,context):
    pair=await _pair(update,context,"ship")
    if not pair:return await update.effective_message.reply_text("☾ I need two known group members before I can make this choice.")
    a,b=pair;s=random.randint(0,100);tier="low" if s<40 else "mid" if s<75 else "high"
    await update.effective_message.reply_text(f"🚢 {mention(a['id'],a['name'])} + {mention(b['id'],b['name'])}\n\nShip name: *{_ship_name(a['name'],b['name'])}*\n{'❤️'*(s//10)}{'🖤'*(10-s//10)} {s}%\n_{random.choice(SHIP_VERDICTS[tier])}_",parse_mode="Markdown")

async def random_ship(update,context):
    pair=await _pair(update,context,"randomship")
    if not pair:return await update.effective_message.reply_text("☾ Not enough known members yet — let the room breathe a little first.")
    a,b=pair
    await update.effective_message.reply_text(f"🎲 {mention(a['id'],a['name'])} + {mention(b['id'],b['name'])} — *{random.randint(0,100)}%* match",parse_mode="Markdown")

async def track_message(update,context):
    if not update.effective_chat or not update.effective_user:return
    chat_id=update.effective_chat.id;user=update.effective_user
    entry=message_counts.setdefault(chat_id,{}).setdefault(user.id,{"name":user.first_name or "someone","count":0,"is_bot":bool(user.is_bot)})
    entry["name"]=user.first_name or entry.get("name") or "someone";entry["count"]=int(entry.get("count",0))+1

async def bestie(update,context):
    pair=await _pair(update,context,"bestie")
    if not pair:return await update.effective_message.reply_text("☾ I need two known members before Oracle can choose the bestie bond.")
    u1,u2=pair;chat_id=update.effective_chat.id
    class Person:
        def __init__(self,d):self.id=d["id"];self.first_name=d["name"]
    p1,p2=Person(u1),Person(u2);declared_besties.setdefault(chat_id,{})[p1.id]=p2;declared_besties[chat_id][p2.id]=p1
    await update.effective_message.reply_text(f"💛 {mention(p1.id,p1.first_name)} & {mention(p2.id,p2.first_name)} are now official besties!",parse_mode="Markdown")

async def duo(update,context):
    pair=await _pair(update,context,"duo")
    if not pair:return await update.effective_message.reply_text("☾ I need two known members before I can forge a duo.")
    a,b=pair;await update.effective_message.reply_text(f"🔗 {mention(a['id'],a['name'])} + {mention(b['id'],b['name'])} = *{random.choice(DUO_PREFIXES)} {random.choice(DUO_SUFFIXES)}*",parse_mode="Markdown")

async def friendship_score(update,context):
    pair=await _pair(update,context,"friendship")
    if not pair:return await update.effective_message.reply_text("☾ I need two known members before Oracle can read the friendship.")
    a,b=pair;await update.effective_message.reply_text(f"💫 {mention(a['id'],a['name'])} + {mention(b['id'],b['name'])}: *{random.randint(40,100)}%* compatible",parse_mode="Markdown")

async def tag_bestie(update,context):
    actor=update.effective_user;b=declared_besties.get(update.effective_chat.id,{}).get(actor.id if actor else 0)
    if not b:return await update.effective_message.reply_text("☾ No declared bestie yet — /bestie lets Oracle choose one.")
    await update.effective_message.reply_text(f"📣 {mention(actor.id,actor.first_name)} is calling {mention(b.id,b.first_name)}",parse_mode="Markdown")

async def squad(update,context):
    top=sorted(message_counts.get(update.effective_chat.id,{}).items(),key=lambda x:x[1]["count"],reverse=True)[:4]
    if not top:return await update.effective_message.reply_text("☾ Not enough activity data yet.")
    await update.effective_message.reply_text("👥 Squad:\n"+", ".join(mention(i,d["name"]) for i,d in top),parse_mode="Markdown")

async def loyalty(update,context):
    target=await _single_target(update,context,"loyalty",allow_self=True)
    if not target:return await update.effective_message.reply_text("☾ I need a known member before I can read loyalty.")
    await update.effective_message.reply_text(f"🛡️ {mention(target['id'],target['name'])}'s loyalty score: *{random.randint(60,100)}/100*",parse_mode="Markdown")

async def matchmaker(update,context): await random_ship(update,context)
async def friendship_test(update,context): await friendship_score(update,context)

ACTIONS={"hug":("🤗 wraps {target} in a warm hug","anime hug"),"pat":("🖐️ gives {target} a gentle head pat","head pat anime"),"highfive":("🙌 high-fives {target}","high five"),"slap":("👋 slaps {target}","anime slap"),"kiss":("😘 kisses {target}","anime kiss"),"poke":("👉 pokes {target}","anime poke"),"cuddle":("🥺 cuddles up with {target}","anime cuddle"),"wave":("👋 waves at {target}","anime wave hello"),"bite":("😬 playfully bites {target}","anime bite"),"tickle":("🤣 tickles {target}","anime tickle"),"kick":("🦵 gives {target} a playful kick","anime kick"),"punch":("👊 throws a playful punch at {target}","anime punch"),"bonk":("🔨 bonks {target}","anime bonk"),"dance":("💃 dances with {target}","anime dance"),"cheer":("📣 cheers for {target}","anime cheer"),"comfort":("🫂 comforts {target}","anime comfort"),"salute":("🫡 salutes {target}","anime salute"),"stare":("👀 stares dramatically at {target}","anime stare"),"handshake":("🤝 shakes hands with {target}","anime handshake"),"fistbump":("👊 fist-bumps {target}","fist bump anime"),"shoulderpat":("🫳 pats {target}'s shoulder","shoulder pat anime"),"cheers":("🥂 cheers with {target}","anime cheers"),"wink":("😉 winks at {target}","anime wink")}

async def _action(update,context,key):
    target=await _single_target(update,context,key)
    if not target:return await update.effective_message.reply_text(f"☾ I need another known member before Oracle can choose someone for /{key}.")
    actor=update.effective_user;text,gif=ACTIONS[key]
    from handlers.chat import send_text_with_gif
    actor_name=mention(actor.id,actor.first_name) if actor else "☾ Oracle"
    await send_text_with_gif(context.bot,update.effective_chat.id,f"{actor_name} {text.format(target=mention(target['id'],target['name']))}",gif)

def _make_action(key):
    async def handler(update,context): await _action(update,context,key)
    handler.__name__=key;return handler

for _key in ACTIONS:
    if _key not in globals():globals()[_key]=_make_action(_key)

from handlers.fun import roast
