import random
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention

bestie_pairs={};declared_besties={};message_counts={}
DUO_PREFIXES=["Chaos","Dream","Menace","Golden","Rogue"];DUO_SUFFIXES=["Duo","Squad","Twins","Crew"]
SHIP_VERDICTS={"low":["chaotic and doomed 💀","friends at best, enemies at worst 😭"],"mid":["could work with effort 🤞","50/50, coin flip energy"],"high":["written in the stars ✨","unreasonably perfect together"]}
def _ship_name(a,b):return (a[:max(1,len(a)//2)]+b[len(b)//2:]).title()
async def ship(update,context):
    if update.message.reply_to_message:u1,u2=update.effective_user,update.message.reply_to_message.from_user;a,b=u1.first_name,u2.first_name;m1,m2=mention(u1.id,a),mention(u2.id,b)
    elif len(context.args)>=2:a,b=context.args[:2];m1,m2=a,b
    else:return await update.message.reply_text("Usage: reply to someone with /ship, or /ship [name1] [name2]")
    s=random.randint(0,100);tier="low" if s<40 else "mid" if s<75 else "high";await update.message.reply_text(f"🚢 {m1} + {m2}\n\nShip name: *{_ship_name(a,b)}*\n{'❤️'*(s//10)}{'🖤'*(10-s//10)} {s}%\n_{random.choice(SHIP_VERDICTS[tier])}_",parse_mode="Markdown")
async def random_ship(update,context):
    pool=list(message_counts.get(update.effective_chat.id,{}).items())
    if len(pool)<2:return await update.message.reply_text("Not enough active members tracked yet — chat a bit more first!")
    (i1,d1),(i2,d2)=random.sample(pool,2);await update.message.reply_text(f"🎲 {mention(i1,d1['name'])} + {mention(i2,d2['name'])} — *{random.randint(0,100)}%* match",parse_mode="Markdown")
async def track_message(update,context):
    if not update.effective_chat or not update.effective_user:return
    c=update.effective_chat.id;u=update.effective_user;message_counts.setdefault(c,{}).setdefault(u.id,{"name":u.first_name,"count":0})["count"]+=1
async def bestie(update,context):
    if not update.message.reply_to_message:return await update.message.reply_text("Reply to your bestie's message with /bestie")
    u1=update.effective_user;u2=update.message.reply_to_message.from_user;c=update.effective_chat.id;declared_besties.setdefault(c,{})[u1.id]=u2;declared_besties[c][u2.id]=u1;await update.message.reply_text(f"💛 {mention(u1.id,u1.first_name)} & {mention(u2.id,u2.first_name)} are now official besties!",parse_mode="Markdown")
async def duo(update,context):
    if not update.message.reply_to_message:return await update.message.reply_text("Reply to someone's message with /duo to generate a duo name")
    u1=update.effective_user;u2=update.message.reply_to_message.from_user;await update.message.reply_text(f"🔗 {mention(u1.id,u1.first_name)} + {mention(u2.id,u2.first_name)} = *{random.choice(DUO_PREFIXES)} {random.choice(DUO_SUFFIXES)}*",parse_mode="Markdown")
async def friendship_score(update,context):
    if not update.message.reply_to_message:return await update.message.reply_text("Reply to someone's message with /friendship")
    u1=update.effective_user;u2=update.message.reply_to_message.from_user;await update.message.reply_text(f"💫 {mention(u1.id,u1.first_name)} + {mention(u2.id,u2.first_name)}: *{random.randint(40,100)}%* compatible",parse_mode="Markdown")
async def tag_bestie(update,context):
    b=declared_besties.get(update.effective_chat.id,{}).get(update.effective_user.id)
    if not b:return await update.message.reply_text("You haven't declared a bestie yet — use /bestie first")
    await update.message.reply_text(f"📣 {mention(update.effective_user.id,update.effective_user.first_name)} is calling {mention(b.id,b.first_name)}",parse_mode="Markdown")
async def squad(update,context):
    top=sorted(message_counts.get(update.effective_chat.id,{}).items(),key=lambda x:x[1]["count"],reverse=True)[:4]
    await update.message.reply_text("👥 Squad:\n"+", ".join(mention(i,d["name"]) for i,d in top),parse_mode="Markdown") if top else await update.message.reply_text("Not enough activity data yet.")
async def loyalty(update,context):
    t=update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user;await update.message.reply_text(f"🛡️ {mention(t.id,t.first_name)}'s loyalty score: *{random.randint(60,100)}/100*",parse_mode="Markdown")
async def matchmaker(update,context):await random_ship(update,context)
async def friendship_test(update,context):await friendship_score(update,context)
ACTIONS={"hug":("🤗 wraps {target} in a warm hug","anime hug"),"pat":("🖐️ gives {target} a gentle head pat","head pat anime"),"highfive":("🙌 high-fives {target}","high five"),"slap":("👋 slaps {target}","anime slap"),"kiss":("😘 kisses {target}","anime kiss"),"poke":("👉 pokes {target}","anime poke"),"cuddle":("🥺 cuddles up with {target}","anime cuddle"),"wave":("👋 waves at {target}","anime wave hello"),"bite":("😬 playfully bites {target}","anime bite"),"tickle":("🤣 tickles {target}","anime tickle"),"kick":("🦵 gives {target} a playful kick","anime kick"),"punch":("👊 throws a playful punch at {target}","anime punch"),"bonk":("🔨 bonks {target}","anime bonk"),"dance":("💃 dances with {target}","anime dance"),"cheer":("📣 cheers for {target}","anime cheer"),"comfort":("🫂 comforts {target}","anime comfort"),"salute":("🫡 salutes {target}","anime salute"),"stare":("👀 stares dramatically at {target}","anime stare"),"handshake":("🤝 shakes hands with {target}","anime handshake"),"fistbump":("👊 fist-bumps {target}","fist bump anime"),"shoulderpat":("🫳 pats {target}'s shoulder","shoulder pat anime"),"cheers":("🥂 cheers with {target}","anime cheers"),"wink":("😉 winks at {target}","anime wink")}
async def _action(update,context,key):
    if not update.message.reply_to_message:return await update.message.reply_text(f"Reply to someone's message with /{key}")
    actor=update.effective_user;target=update.message.reply_to_message.from_user;text,gif=ACTIONS[key];from handlers.chat import send_text_with_gif;await send_text_with_gif(context.bot,update.effective_chat.id,f"{mention(actor.id,actor.first_name)} {text.format(target=mention(target.id,target.first_name))}",gif)

def _make_action(key):
    async def handler(update,context):await _action(update,context,key)
    handler.__name__=key;return handler
for _key in ACTIONS:
    if _key not in globals():globals()[_key]=_make_action(_key)
