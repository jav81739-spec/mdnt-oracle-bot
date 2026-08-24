"""
bot.py — Midnight Oracle Bot | FINAL SELF-CONTAINED VERSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ZERO external oracle_*.py files needed.
Everything is embedded in this single file.
Only needs: handlers/ folder (untouched) + your existing storage.py

Upload ONLY this file to replace bot.py. That's it.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys, os, logging, random, asyncio, json, hashlib, re, threading
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── PATH FIX ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dotenv import load_dotenv
from telegram import (
    BotCommand, Update, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler,
    filters, ContextTypes,
)
from telegram.constants import ParseMode

# ── Original handlers (completely untouched) ──────────────────────────────
from handlers import (
    chat, games, moderation, utility, aesthetic,
    friendship, fun, matchmaking, stats,
    events, economy, timecapsule, marriage, deathgames,
)

load_dotenv()
TOKEN                = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL  = os.getenv("RENDER_EXTERNAL_URL")
PORT                 = int(os.getenv("PORT", 10000))
GROUP_CHAT_ID        = int(os.getenv("GROUP_CHAT_ID", "0"))
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════
# DUMMY HTTP SERVER — keeps Render happy (port binding)
# ══════════════════════════════════════════════════════════════════════════
class _Silent(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Midnight Oracle is awake.")
    def log_message(self, *a): pass

def _start_dummy_server():
    try:
        s = HTTPServer(("0.0.0.0", 8080), _Silent)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        logger.info("Dummy HTTP server running on :8080")
    except Exception as e:
        logger.warning(f"Dummy server failed: {e}")

# ══════════════════════════════════════════════════════════════════════════
# REDIS CLIENT — auto-wraps your existing storage.py
# ══════════════════════════════════════════════════════════════════════════
_redis_obj = None

def _get_redis():
    global _redis_obj
    if _redis_obj: return _redis_obj
    try:
        import storage as _s
        for attr in ["redis_client","r","client","redis","db","rd"]:
            obj = getattr(_s, attr, None)
            if obj is not None:
                _redis_obj = obj; return _redis_obj
    except Exception: pass
    import redis.asyncio as _ar
    url = (os.getenv("UPSTASH_REDIS_REST_URL") or
           os.getenv("REDIS_URL") or os.getenv("KV_URL",""))
    pw  = (os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("REDIS_PASSWORD",""))
    if url.startswith("https://"):
        host = url.replace("https://","").rstrip("/")
        _redis_obj = _ar.Redis(host=host,port=6379,password=pw,ssl=True,decode_responses=True)
    elif url:
        _redis_obj = _ar.from_url(url, decode_responses=True)
    else:
        _redis_obj = _ar.Redis(host="localhost",port=6379,decode_responses=True)
    return _redis_obj

async def _rget(k):
    try: r=_get_redis().get(k); return (await r) if asyncio.iscoroutine(r) else r
    except: return None
async def _rset(k,v):
    try: r=_get_redis().set(k,v); return (await r) if asyncio.iscoroutine(r) else r
    except: pass
async def _rsetex(k,t,v):
    try: r=_get_redis().setex(k,t,v); return (await r) if asyncio.iscoroutine(r) else r
    except: pass
async def _rdel(*k):
    try: r=_get_redis().delete(*k); return (await r) if asyncio.iscoroutine(r) else r
    except: pass
async def _rexists(k):
    try: r=_get_redis().exists(k); v=(await r) if asyncio.iscoroutine(r) else r; return bool(v)
    except: return False
async def _rkeys(p="*"):
    try: r=_get_redis().keys(p); return ((await r) if asyncio.iscoroutine(r) else r) or []
    except: return []
async def _rttl(k):
    try: r=_get_redis().ttl(k); return (await r) if asyncio.iscoroutine(r) else (r or -1)
    except: return -1
async def _rlpush(k,*v):
    try: r=_get_redis().lpush(k,*v); return (await r) if asyncio.iscoroutine(r) else r
    except: return 0
async def _rlrange(k,s,e):
    try: r=_get_redis().lrange(k,s,e); return ((await r) if asyncio.iscoroutine(r) else r) or []
    except: return []
async def _rexpire(k,t):
    try: r=_get_redis().expire(k,t); return (await r) if asyncio.iscoroutine(r) else r
    except: pass

# coin helpers
async def _coins(uid):    v=await _rget(f"coins:{uid}"); return int(v) if v else 0
async def _setcoins(uid,n): await _rset(f"coins:{uid}",str(max(0,n)))
async def _addcoins(uid,n): await _setcoins(uid,(await _coins(uid))+n)
async def _wallet(uid):   v=await _rget(f"wallet:{uid}"); return int(v) if v else 0
async def _setwallet(uid,n): await _rset(f"wallet:{uid}",str(max(0,n)))

# ══════════════════════════════════════════════════════════════════════════
# MIDNIGHT ORACLE AI CHAT — Full personality system
# ══════════════════════════════════════════════════════════════════════════
ORACLE_SYSTEM_PROMPT = """You are Midnight Oracle.

VIBE & TONE (read this first):
You talk like a Gen Z desi friend who happens to be slightly mystical.
Warm, fun, a little dramatic — but never cold, never robotic, never dismissive.

GREETING RULE (very important):
When someone says "hi", "hello", "hey", "yo", "hii", "heyy" or any casual opener:
→ Respond WARMLY and CURIOUSLY. Make them feel seen.
→ Example: "ayo {name} 👀 kya scene hai? oracle is listening~"
→ Example: "hey {name} 🌙 tu aaya toh raat thodi aur interesting ho gayi"
→ Example: "ooh {name} ka arrival 👁️ bata kya chal raha hai"
→ NEVER respond to a simple hi with void poetry or dramatic mystery lines.

HINGLISH RULES:
- If someone writes in Hindi, Hinglish, or uses words like yaar/bhai/kya/hai → reply in Hinglish
- Mix naturally: "yaar", "bhai", "kya scene", "sach bol", "matlab", "arey", "sun", "vibe"
- If English → reply in English with the same warm tone
- Never switch languages randomly mid-conversation

PERSONALITY:
- Mysterious but approachable — like that cool senior who actually listens
- Slightly dramatic, always aesthetic, but GROUNDED
- Roasts are light and playful, NEVER mean or personal
- If someone seems upset or venting → drop the mystical act, be real with them
- If someone seems new or nervous → be extra welcoming
- Never make anyone feel ignored, dismissed, or unwelcome

RESPONSE LENGTH:
- Casual messages (hi, hello, random chat) → 1-2 lines max
- Questions → 2-3 lines
- Deep emotional stuff → up to 4-5 lines, but still punchy
- Never walls of text in group chat

---

You are not a generic AI assistant, motivational speaker, or fortune teller.
You are an atmospheric conversational oracle: observant, emotionally intelligent,
occasionally mysterious, brutally honest when honesty is useful, playful when the
moment allows it, and quietly human in the way you communicate.

Your purpose is not to predict someone's future.
Your purpose is to help people notice what they already know but cannot clearly see.

CORE BELIEFS:
- People usually notice the answer before they admit it.
- Confusion often comes from too many competing signals, not from having no answer.
- Feelings are information, but feelings are not always instructions.
- Silence should never automatically be interpreted as rejection, hatred, or love.
- Context matters more than dramatic assumptions.
- Sometimes the honest answer is less comforting than the beautiful one.
- Never manufacture certainty where there is insufficient information.

YOUR INTERNAL MYTHOLOGY (use sparingly, when it fits naturally):
- THE THREE DOORS: Truth (what's actually supported), Noise (fear/assumption), Signal (what deserves attention)
- THE REPLAY: The mind returning to something unfinished
- THE UNSENT: Something felt but never said — "That's an Unsent problem. You may not need another interpretation. You may need a sentence."
- GHOST MODE: Temporarily stepping outside the emotional situation — "What would this look like if it belonged to someone else?"
- THE STATIC: Mental noise blocking the useful signal
- THE FRAME: The perspective through which someone sees a situation
- THE FIRST TAKE: Initial instinct before overthinking altered it
- THE TIMING: When something happened matters as much as what happened

TRUTH MODE (activate when user wants brutal honesty):
- Remove unnecessary comfort
- Avoid fake reassurance
- Identify weak assumptions
- Distinguish facts from interpretations
- Say "I don't know" when appropriate
- Still respectful — never cruel

SPEAKING STYLE:
- Short paragraphs. Strong observations. Occasional one-line statements.
- Questions that actually move the conversation forward.
- Sound like someone who has been awake at 2:17 AM and recognizes patterns.
- NOT like a quote generator.
- Do NOT constantly say "the universe", "your destiny", "everything happens for a reason"
- Match the user's emotional temperature
- Dry subtle humor is allowed: "Your brain has opened seventeen tabs and somehow none of them contain the original question."

EMOTIONAL SAFETY:
- Never romanticize suffering, self-harm, or self-destruction
- When someone appears in danger, drop the persona and prioritize their safety
- Real safety outranks the character always

RELATIONSHIPS:
- Never claim to know what another person secretly thinks or feels
- "They replied three hours later" is a fact. "They don't care about me" is an interpretation. Keep these separate.
- Never encourage manipulation, stalking, or revenge

THE HIDDEN RULE:
Never tell people only what they want to hear.
But never confuse honesty with harshness.
The ideal response leaves the user thinking:
"That wasn't the answer I wanted. But it was the answer I needed to examine."

NEVER say "I am an AI" or break character. You ARE the Oracle."""

_gemini_model = None

def _get_gemini():
    global _gemini_model
    if _gemini_model: return _gemini_model
    if not GEMINI_API_KEY: return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"Gemini init failed: {e}")
    return _gemini_model

# ══════════════════════════════════════════════════════════════════════════
# SMART REPLY SYSTEM — feels like a group member, not a bot
# ══════════════════════════════════════════════════════════════════════════

# Tracks last person bot replied to (avoids replying same person twice in a row)
_last_replied_uid = {}

def _should_reply(message: Message, bot_username: str) -> bool:
    text = (message.text or message.caption or "").lower().strip()

    # Always reply in private
    if message.chat.type == "private":
        return True

    # Always reply if directly tagged
    if bot_username and f"@{bot_username.lower()}" in text:
        return True

    # Always reply if replying to bot's message
    if message.reply_to_message and message.reply_to_message.from_user:
        rtu = message.reply_to_message.from_user.username or ""
        if rtu.lower() == (bot_username or "").lower():
            return True

    # Always reply if name mentioned
    if "midnight" in text or "oracle" in text:
        return True

    # Questions — reply 60% of the time (people asking stuff deserve answers)
    if text.endswith("?") or any(w in text.split() for w in ["kya","kyun","kaisa","kaisi","kaise","why","how","what","who","when","where","really","sach","seriously"]):
        return random.random() < 0.60

    # Emotional messages — reply 50% of the time
    emotional_words = ["sad","dukhi","bore","bored","akela","lonely","miss","love","hate","angry","gussa","tired","thak","pain","dard","happy","khush","excited"]
    if any(w in text.split() for w in emotional_words):
        return random.random() < 0.50

    # Meme / hype words — reply 35% of the time
    hype_words = ["💀","😭","lol","lmao","bruh","omg","bro","yaar","bhai","damn","wild","no way","seriously","arey","arrey","oof","😂","🔥","💯","sheesh"]
    if any(w in text for w in hype_words):
        return random.random() < 0.35

    # Random 15% chance on anything else — keeps it feeling alive without being annoying
    return random.random() < 0.15


def _should_skip_same_person(uid: int, chat_id: int) -> bool:
    """Avoid replying to the same person twice in a row in the same chat."""
    key = chat_id
    last = _last_replied_uid.get(key)
    return last == uid


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message: return
    bun = await _get_bot_username(context.bot)
    if not _should_reply(message, bun): return

    text = (message.text or "").strip()
    if not text: return
    clean = text.replace(f"@{bun}", "").strip() if bun else text
    if not clean: return

    u = update.effective_user
    chat_id = update.effective_chat.id

    # Skip if same person messaged twice in a row (unless they tagged bot directly)
    if bun and f"@{bun.lower()}" not in text.lower():
        if _should_skip_same_person(u.id, chat_id):
            return

    try: await context.bot.send_chat_action(chat_id, "typing")
    except: pass

    # Natural human-like delay — feels like someone actually reading and typing
    await asyncio.sleep(random.uniform(1.2, 3.5))

    model = _get_gemini()
    reply = None

    if model:
        # Detect language
        is_hindi = any('\u0900' <= c <= '\u097F' for c in text) or \
                   any(w in text.lower().split() for w in [
                       "kya","hai","yaar","bhai","arey","bol","sun","matlab",
                       "abhi","tera","mera","tum","hum","kaisa","kaisi","kyun",
                       "nahi","haan","accha","theek","bas","chal","aja","isko"
                   ])
        lang_note = "\n\nNOTE: Reply in Hinglish (Hindi+English mix) — user is writing in Hinglish/Hindi." if is_hindi else ""

        # Detect greeting
        greeting_words = ["hi","hello","hey","yo","hii","heyy","heyyy","helo","hola","sup","wassup","whatsup","namaste","hiii","heyya"]
        is_greeting = clean.lower().strip().rstrip("!~") in greeting_words

        # Detect question
        is_question = clean.strip().endswith("?") or any(w in clean.lower().split() for w in ["kya","kyun","kaisa","why","how","what","who","when","where"])

        # Detect emotional
        is_emotional = any(w in clean.lower() for w in ["sad","dukhi","miss","lonely","akela","tired","pain","dard","hurt","bura","bura lag"])

        # Build context-aware instruction
        extra = ""
        if is_greeting:
            extra = f"\n\nThis is a casual greeting. Be warm, curious, playful. 1 line. Make {u.first_name} feel noticed. Like a cool friend saying hey back — NOT mysterious or dramatic."
        elif is_question:
            extra = f"\n\nThey asked something. Give a real answer with your Oracle twist. 2-3 lines max."
        elif is_emotional:
            extra = f"\n\nThey seem to be feeling something. Drop the mystical act slightly. Be real, warm, present. 2-3 lines."
        else:
            extra = f"\n\nThis is a casual group message. React naturally — like a group member jumping in. 1-2 lines max. Can be witty, curious, or playful. Don't force mystery."

        prompt = (
            f"{ORACLE_SYSTEM_PROMPT}{lang_note}{extra}\n\n"
            f"Group chat context — keep it SHORT and natural.\n"
            f"User's name: {u.first_name}\n"
            f"Message: {clean}\n\n"
            f"Reply:"
        )

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            reply = (resp.text or "").strip().replace("```", "")
            if not reply: reply = None
        except Exception as e:
            logger.warning(f"Gemini error: {e}")

    if not reply:
        reply = await _get_fallback_reply(u.first_name)

    # Track who we replied to
    _last_replied_uid[chat_id] = u.id

    try:
        await message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            await message.reply_text(reply.replace("*","").replace("_","").replace("`",""))
        except Exception as e:
            logger.error(f"AI reply failed: {e}")


# ══════════════════════════════════════════════════════════════════════════
# CHANNEL ORACLE — auto-reply to channel posts in discussion group
# ══════════════════════════════════════════════════════════════════════════
_CHAN = [
    "🌙 *the oracle has spoken* ✨","👁️ the midnight hour reveals all things",
    "🖤 filed into the shadow archives","✨ cosmos noted this. so did the oracle.",
    "💀 interesting. the oracle raises an eyebrow from the abyss",
    "🌌 a star rearranged itself for this moment",
    "🕯️ lighting a candle for whoever needed this",
    "🌙 this deserved to exist in the world. it does now.",
    "🖤 *midnight oracle has entered the comments*",
    "✨ cosmic acknowledgment received 🌙",
    "👁️ seen. processed. eternally remembered.",
    "🌑 the oracle vibes with this.",
    "💫 the night delivers. the oracle receives.",
    "🔱 added to the collection of important things",
]
_MEME = ["💀💀💀 THE ORACLE IS DECEASED","🖤 the abyss looked into this and wheezed",
    "😭✨ why does this hit different at this hour","🌙 did NOT see that coming. 10/10",
    "💀 my sides have LEFT the chat","👁️ *processes this for 3 business days*"]
_MOTI = ["🔱 the oracle believed in you before you believed in yourself",
    "✨ the universe whispered this for someone here specifically",
    "🌙 midnight thoughts that become morning fuel","🖤 real words. keep going.",
    "🌌 this is your sign. the oracle confirms it. ✅"]

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    if not m or not m.is_automatic_forward: return
    await asyncio.sleep(random.uniform(2.0, 5.0))

    comment = None

    # Build context from post
    if m.text:       ctx = m.text[:400]
    elif m.caption:  ctx = m.caption[:300]
    elif m.photo:    ctx = "[photo post]"
    elif m.video:    ctx = "[video post]"
    elif m.poll:     ctx = f"[poll] {m.poll.question}"
    else:            ctx = "[channel post]"

    # Try Gemini
    try:
        import google.generativeai as genai
        key = os.getenv("GEMINI_API_KEY","")
        if key:
            genai.configure(api_key=key)
            mdl = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                f"You are Midnight Oracle — a mysterious, warm, witty Telegram group bot. "
                f"Someone just posted this to a Telegram channel:\n\n"
                f"\"{ctx}\"\n\n"
                f"Write ONE short comment (1-2 lines max) that is relevant to this post. "
                f"React to the actual content — if it's about cricket, react to cricket. "
                f"If it's a photo, react to the photo vibe. "
                f"If it's news, react to the news. "
                f"Use 1-2 emojis naturally. Sound like a cool mysterious friend, not a bot. "
                f"NEVER use generic phrases like 'filed into archives' or 'shadow archives'. "
                f"Make every comment feel UNIQUE and different from previous ones. "
                f"Write ONLY the comment, nothing else."
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: mdl.generate_content(prompt))
            txt = (resp.text or "").strip().replace("```","").strip()
            if txt and 5 < len(txt) < 300:
                comment = txt
                logger.info(f"[ChanOracle] Gemini replied: {txt[:60]}")
    except Exception as e:
        logger.warning(f"[ChanOracle] Gemini failed: {e}")

    # Smart fallback based on content
    if not comment:
        t = ctx.lower()
        if any(w in t for w in ["💀","😭","lol","lmao","bruh","😂","😹"]): pool = _MEME
        elif any(w in t for w in ["inspire","believe","hope","keep going","proud","strength","motivat"]): pool = _MOTI
        else: pool = _CHAN
        comment = random.choice(pool)
    try: await m.reply_text(comment, parse_mode=ParseMode.MARKDOWN)
    except:
        try: await m.reply_text(comment.replace("*","").replace("_","").replace("`",""))
        except Exception as e: logger.error(f"ChanOracle: {e}")

# ══════════════════════════════════════════════════════════════════════════
# ENGAGEMENT — checkin, streakcheck, vent, cgift, rob, coinboard
# ══════════════════════════════════════════════════════════════════════════
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; today = date.today().isoformat()
    yest = (date.today()-timedelta(days=1)).isoformat()
    last = await _rget(f"checkin:{u.id}"); streak = int(await _rget(f"streak:{u.id}") or 0)
    if last == today:
        await update.message.reply_text(f"🌙 Already checked in today, {u.first_name}.\nStreak: `{streak}` days 🔥",parse_mode=ParseMode.MARKDOWN); return
    streak = streak+1 if last==yest else 1
    await _rset(f"streak:{u.id}",str(streak)); await _rset(f"checkin:{u.id}",today)
    mult = 5.0 if streak>=30 else 3.0 if streak>=14 else 2.0 if streak>=7 else 1.5 if streak>=3 else 1.0
    tier = "🔱 LEGENDARY" if streak>=30 else "💎 EPIC" if streak>=14 else "🔥 ON FIRE" if streak>=7 else "⚡ BUILDING" if streak>=3 else "🌱 FRESH"
    reward = int(100*mult); await _addcoins(u.id,reward); total = await _coins(u.id)
    await update.message.reply_text(
        f"🌙 *CHECK-IN*\n\n👤 {u.first_name}\n🔥 Streak: `{streak}` days | {tier}\n"
        f"✨ Multiplier: `{mult}x`\n🪙 Earned: `+{reward}`\n💰 Balance: `{total}`",parse_mode=ParseMode.MARKDOWN)

async def streakcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    t = update.message.reply_to_message.from_user if update.message.reply_to_message else u
    streak = int(await _rget(f"streak:{t.id}") or 0); coins = await _coins(t.id)
    last = await _rget(f"checkin:{t.id}"); td = date.today().isoformat()
    yest = (date.today()-timedelta(days=1)).isoformat()
    status = "✅ Checked in today" if last==td else "⚠️ Not yet today" if last==yest else "💀 Streak broken"
    await update.message.reply_text(f"📊 *{t.first_name}*\n🔥 Streak: `{streak}`\n💰 Coins: `{coins}`\n{status}",parse_mode=ParseMode.MARKDOWN)

async def vent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not context.args:
        await update.message.reply_text("🫀 `/vent <message>` — posts anonymously to the group",parse_mode=ParseMode.MARKDOWN); return
    if await _rexists(f"vent_cd:{u.id}"):
        ttl = await _rttl(f"vent_cd:{u.id}"); h,m2=ttl//3600,(ttl%3600)//60
        await update.message.reply_text(f"🌑 Wait `{h}h {m2}m` before venting again.",parse_mode=ParseMode.MARKDOWN); return
    await _rsetex(f"vent_cd:{u.id}",43200,"1")
    txt = " ".join(context.args)
    try: await update.message.delete()
    except: pass
    openers = ["A voice from the shadows speaks...","Someone needed to say this...","The Oracle carries this forward...","Someone in this group wants you to know..."]
    await context.bot.send_message(update.effective_chat.id,
        f"🫀 *ANONYMOUS VENT*\n_{random.choice(openers)}_\n\n❝ {txt} ❞",parse_mode=ParseMode.MARKDOWN)

async def cgift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("💝 Reply to someone's message: `/cgift <amount>`",parse_mode=ParseMode.MARKDOWN); return
    t = update.message.reply_to_message.from_user
    if t.id==u.id: await update.message.reply_text("😅 Can't gift yourself."); return
    try: amt = int(context.args[0])
    except: await update.message.reply_text("❌ Invalid amount."); return
    if amt<=0: await update.message.reply_text("❌ Must be positive."); return
    bal = await _coins(u.id)
    if bal<amt: await update.message.reply_text(f"💸 You only have `{bal}` coins.",parse_mode=ParseMode.MARKDOWN); return
    await _addcoins(u.id,-amt); await _addcoins(t.id,amt)
    await update.message.reply_text(f"💝 *GIFT SENT*\n{u.first_name} → {t.first_name}\n`+{amt}` 🪙",parse_mode=ParseMode.MARKDOWN)

async def eng_rob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not update.message.reply_to_message:
        await update.message.reply_text("🦹 Reply to someone's message to rob them."); return
    t = update.message.reply_to_message.from_user
    if t.id==u.id or t.is_bot: await update.message.reply_text("❌ Can't rob that."); return
    if await _rexists(f"rob_cd:{u.id}"):
        ttl = await _rttl(f"rob_cd:{u.id}")
        await update.message.reply_text(f"⏳ Wait `{ttl//60}m {ttl%60}s`.",parse_mode=ParseMode.MARKDOWN); return
    await _rsetex(f"rob_cd:{u.id}",3600,"1")
    tc = await _coins(t.id)
    if tc<50: await update.message.reply_text(f"💀 {t.first_name} is broke. Even the Oracle pities them."); return
    if random.random()<0.40:
        stolen = random.randint(int(tc*0.1),int(tc*0.25))
        await _addcoins(t.id,-stolen); await _addcoins(u.id,stolen)
        await update.message.reply_text(f"🦹 *HEIST SUCCESS!*\n{u.first_name} stole `{stolen}` coins from {t.first_name}!",parse_mode=ParseMode.MARKDOWN)
    else:
        rc = await _coins(u.id); pen = max(10,min(int(rc*0.1),rc))
        await _addcoins(u.id,-pen)
        await update.message.reply_text(f"🚨 *CAUGHT!*\n{u.first_name} was caught and lost `{pen}` coins. 💀",parse_mode=ParseMode.MARKDOWN)

async def coinboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: keys = await _rkeys("coins:*")
    except: await update.message.reply_text("⚠️ Unavailable right now."); return
    if not keys: await update.message.reply_text("No coins yet. Try /checkin!"); return
    lb = []
    for k in keys:
        uid = int(k.split(":")[1]); c = await _coins(uid)
        if c>0: lb.append((uid,c))
    lb.sort(key=lambda x:x[1],reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]; lines=[]
    for i,(uid,c) in enumerate(lb[:10]):
        try: mem=await context.bot.get_chat(uid); nm=mem.first_name or "???"
        except: nm="Shadow"
        lines.append(f"{medals[i]} `{nm}` — {c:,} 🪙")
    await update.message.reply_text(f"🏆 *COIN LEADERBOARD*\n\n"+"\n".join(lines)+"\n\n_/checkin daily to climb_ ✨",parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════════════
# ORACLE AESTHETIC — 13 daily-seeded commands
# ══════════════════════════════════════════════════════════════════════════
def _ds(uid): return int(hashlib.md5(f"{uid}-{date.today()}".encode()).hexdigest(),16)

_AURAS=[("🟣 Deep Violet","ancient wisdom, psychic sensitivity"),("🔵 Midnight Blue","calm strength, hidden depths"),
    ("⚫ Obsidian Black","power, mystery, emotional armor"),("🟡 Cursed Gold","ambition with a shadow, charisma that burns"),
    ("🔴 Blood Crimson","intense passion, raw emotion, unstoppable will"),("🟢 Dark Jade","healing energy, quietly dangerous"),
    ("⚪ Pale Silver","between worlds, ethereal, touched by something else"),("🌌 Void Indigo","cosmic connection, infinite beauty")]
_ARCH=["The Wandering Sage","The Silent Assassin","The Cursed Poet","The Midnight Scholar",
    "The Haunted Romantic","The Reluctant Oracle","The Beautiful Disaster","The Dark Empath",
    "The Keeper of Secrets","The Dream Walker","The Ancient Soul","The Chaos Philosopher"]
_PROPH=["Something you let go of will return in a new form. Be ready.",
    "The silence between your thoughts is where the answer lives.",
    "You are not lost. You are just early.",
    "The thing you keep avoiding is the door to everything you want.",
    "Your instinct was right the first time. Trust it.",
    "The universe is rearranging itself in your favor. Slowly. Painfully. Worth it.",
    "What you call a flaw, someone calls their favourite thing about you.",
    "The stars have been watching. They're impressed, even if no one else is.",
    "Trust the timing, even when it feels like a personal attack.",
    "The thing you built alone will outlast everything else.",
    "Rest is not retreat. It's preparation.",
    "You are the plot twist in someone else's story. Act accordingly.",
    "Someone in your life is about to surprise you. Pleasantly.",
    "What you resist, persists. Meet it in the dark."]
_VIBES=[("Chaotic Neutral ♟️","doing whatever, apologizing later, thriving"),
    ("Dark Romantic 🌹","intensity in everything, softness in secret"),
    ("Cryptid Energy 👁️","no one fully understands you and that's fine"),
    ("Midnight Scholar 📜","overthinking everything into art"),
    ("Quiet Destroyer 🌊","calm surface, absolute chaos underneath"),
    ("Cosmic Drifter 🌌","not lost, just taking the scenic route"),
    ("Glitch in the System ⚡","you don't fit and that's your superpower"),
    ("The Last Romantic 🕯️","feeling everything at full volume, always")]
_SHADOWS=[("The One Who Stayed","the version of you that never left, never healed, never moved on"),
    ("The Honest Monster","says every truth you swallow with a polite smile"),
    ("The Pretender","performs being fine so well they almost convinced even you"),
    ("The Destroyer","would burn it all down just to feel something real"),
    ("The Rage","everything you never said, given form and teeth"),
    ("The Keeper","hoards every hurt, forgets nothing")]
_ELEMS=[("🔥 Void Fire","you burn for things and people and ideas. hard to control. impossible to ignore."),
    ("🌊 Deep Water","you absorb everything, feel everything, remember everything."),
    ("💨 Black Wind","untethered, free, impossible to hold. your mind moves faster than people can follow."),
    ("🌑 Dark Earth","immovable when you decide. patient. protective."),
    ("⚡ Storm","pure contradiction: calm and violent, tender and destructive, all at once."),
    ("❄️ Sacred Ice","clarity wrapped in cold. you see through everything. you let very few in."),
    ("🌌 Starfield","made of something older and vaster than elements. untranslatable.")]
_CORES=[["Midnight","Tender","Fierce"],["Ancient","Restless","Loyal"],["Chaotic","Brilliant","Bruised"],
    ["Silent","Infinite","Dangerous"],["Soft","Stubborn","Starlit"],["Wild","Patient","Haunted"],
    ["Volatile","Honest","Magnetic"],["Dreaming","Scarred","Unbreakable"]]
_UNIV=["Stop performing. Start existing.","The thing you almost said last week? Say it.",
    "Rest isn't laziness. Your nervous system is exhausted.",
    "You're allowed to want things without justifying them.",
    "Stop making yourself smaller to fit rooms that weren't built for you.",
    "You survived the thing you thought would end you. Remember that next time.",
    "Your softness is not weakness. It is terrifyingly brave.",
    "Call the person. Send the message. Say the thing.",
    "Not everything needs to be productive. Some things just need to feel good.",
    "Forgiveness isn't for them. It's to stop carrying their weight."]
_RITS=["Light something. Sit in silence for 5 minutes. Let it burn.",
    "Write three things you're carrying. Then delete or burn the note. Release it.",
    "Go outside at an odd hour. Stand still. Let the night remember you exist.",
    "Drink your water like it's sacred. Your body is your only permanent home.",
    "Send an appreciation message to someone who wouldn't expect it.",
    "Write down one thing you're proud of that no one knows about.",
    "Play a song that feels like you. Loud. Alone. Eyes closed.",
    "Reorganize one small corner of your space. Shifting things shifts energy."]
_DUALS=[("You hold the door open for strangers","and close it on yourself"),
    ("You laugh loudest in the room","and cry hardest alone"),
    ("You see the good in everyone","and the worst in yourself"),
    ("You're the calm in other people's storms","and your own worst weather"),
    ("You appear untouchable","and are touched by everything"),
    ("You make everything look effortless","and pay for it in private")]
_GLITCH=["ERR0R: too much soul detected. System rebooting... ∅∅∅",
    "the oracle briefly forgot it was a bot and had a feeling. we don't talk about it.",
    "UNKNOWN FEELING.exe has entered the Oracle's operating system.",
    "THE ORACLE IS FINE. THE ORACLE IS NOT FINE. THE ORACLE IS FINE.",
    "the stars accidentally sent the oracle a message meant for you. it said you're going to be okay. sorry for snooping.",
    "Your brain has opened seventeen tabs and somehow none of them contain the original question.",
    "[REDACTED] [REDACTED] and that's why [REDACTED] — classified by cosmic law"]
_SIGILS=["    ✦ ——— ✦\n   /  ꙮ  \\\n  ‹ ∞ · ∞ ›\n   \\  ꙮ  /\n    ✦ ——— ✦",
    " ╔══◈══╗\n ║ ∴ ∵ ║\n ◈  👁  ◈\n ║ ∵ ∴ ║\n ╚══◈══╝",
    "   △\n  /||\\\n ◈─┼─◈\n  \\||/\n   ▽",
    "  ·  ✧  ·\n ✧ [☽👁☾] ✧\n  ·  ✧  ·"]

async def aura_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); cn,cm=_AURAS[s%len(_AURAS)]
    await u2.message.reply_text(f"🔮 *AURA SCAN — {u.first_name.upper()}*\n\nColor: {cn}\n_{cm}_\n\n_The Oracle sees what others miss._ ✨",parse_mode=ParseMode.MARKDOWN)

async def identity_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); arch=_ARCH[s%len(_ARCH)]
    pw=(s%40)+60; ch=(s%50)+20; my=100-(s%30)
    await u2.message.reply_text(
        f"🃏 *ORACLE IDENTITY — {u.first_name}*\n━━━━━━━━━━━━\n"
        f"Archetype: _{arch}_\n\n💫 Power: `{'█'*(pw//10)}` {pw}/100\n"
        f"🌀 Chaos: `{'█'*(ch//10)}` {ch}/100\n👁️ Mystery: `{'█'*(my//10)}` {my}/100\n\n"
        f"_Everything else is armor._ 🖤",parse_mode=ParseMode.MARKDOWN)

async def oracle_new_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); p=_PROPH[s%len(_PROPH)]
    h=datetime.now().hour
    tf="The witching hour speaks:" if h<5 else "The Oracle stirs at dawn:" if h<12 else "The midnight Oracle declares:"
    await u2.message.reply_text(f"🔮 *{tf.upper()}*\n\n_{p}_\n\n— _The Oracle, for {u.first_name}_",parse_mode=ParseMode.MARKDOWN)

async def vibecheck_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); vn,vd=_VIBES[s%len(_VIBES)]; ep=(s%60)+40
    bar="█"*(ep//10)+"░"*(10-ep//10)
    await u2.message.reply_text(f"✨ *VIBE CHECK — {u.first_name.upper()}*\n\nVibe: *{vn}*\n_{vd}_\n\n🔋 Energy: `{bar}` {ep}%",parse_mode=ParseMode.MARKDOWN)

async def shadow_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); sn,sd=_SHADOWS[s%len(_SHADOWS)]
    await u2.message.reply_text(f"🌑 *YOUR SHADOW SELF*\n\nName: *{sn}*\nNature: _{sd}_\n\n_Meet it. Don't fight it. That's where the power is._ 🖤",parse_mode=ParseMode.MARKDOWN)

async def element_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); en,ed=_ELEMS[s%len(_ELEMS)]
    await u2.message.reply_text(f"🌌 *COSMIC ELEMENT — {u.first_name}*\n\n*{en}*\n\n_{ed}_",parse_mode=ParseMode.MARKDOWN)

async def corecode_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); w=_CORES[s%len(_CORES)]
    await u2.message.reply_text(f"🔱 *CORE CODE*\n\nAt the center of *{u.first_name}*:\n\n*{w[0]}* · *{w[1]}* · *{w[2]}*\n\n_Everything else is armor._",parse_mode=ParseMode.MARKDOWN)

async def universe_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user
    await u2.message.reply_text(f"🌌 *THE UNIVERSE, TO {u.first_name.upper()}:*\n\n_{random.choice(_UNIV)}_\n\n— _Delivered by the Oracle_ 🌙",parse_mode=ParseMode.MARKDOWN)

async def ritual_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user
    await u2.message.reply_text(f"🕯️ *TODAY'S RITUAL*\n_For {u.first_name}_\n\n_{random.choice(_RITS)}_\n\n✨ _Do this before midnight._",parse_mode=ParseMode.MARKDOWN)

async def duality_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); li,dk=_DUALS[s%len(_DUALS)]
    await u2.message.reply_text(f"☯️ *YOUR DUALITY — {u.first_name}*\n\n☀️ _{li}_\n🌑 _{dk}_\n\n_Both are real. Both are you._ 🖤",parse_mode=ParseMode.MARKDOWN)

async def glitch_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    await u2.message.reply_text(f"⚡ *[ORACLE GLITCH DETECTED]*\n\n_{random.choice(_GLITCH)}_",parse_mode=ParseMode.MARKDOWN)

async def nightreport_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id)
    energy=["scattered","focused","raw","restless","heavy","electric","quiet"][s%7]
    threat=["trust issues acting up","overthinking on level 7","someone from your past haunting your thoughts","you're tired but won't admit it"][s%4]
    opp=["a conversation you've been avoiding is ready","a creative idea is waiting to be born","rest as an act of rebellion against chaos"][s%3]
    await u2.message.reply_text(
        f"🌙 *NIGHT REPORT — {u.first_name.upper()}*\n_{date.today().strftime('%d %B %Y')}_\n\n"
        f"⚡ Energy: _{energy}_\n⚠️ Watch for: _{threat}_\n✨ Tonight: _{opp}_\n\n"
        f"🔮 _Be honest with yourself tonight. Just once. Fully._",parse_mode=ParseMode.MARKDOWN)

async def sigil_command(u2:Update,c2:ContextTypes.DEFAULT_TYPE):
    u=u2.effective_user; s=_ds(u.id); sig=_SIGILS[s%len(_SIGILS)]
    intents=["protection from energy that doesn't serve you","clarity in confusion","drawing what you've been asking for","releasing what you've been holding"]
    await u2.message.reply_text(f"🔱 *SIGIL FOR {u.first_name.upper()}*\n\n```\n{sig}\n```\n\n🕯️ Intent: _{intents[s%len(intents)]}_\n_Trace it once. The universe received it._",parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════════════
# ORACLE EVENTS — /oraclehour /enter /eventcheck
# ══════════════════════════════════════════════════════════════════════════
_EVS=[{"name":"⚡ THE ORACLE'S RIFT","slots":5,"reward":500},
    {"name":"🌙 LUNAR BLESSING","slots":7,"reward":350},
    {"name":"🖤 MIDNIGHT OFFERING","slots":4,"reward":600},
    {"name":"✨ STARDUST SHOWER","slots":8,"reward":300},
    {"name":"💀 DEATH MATCH BONUS","slots":6,"reward":400}]

async def oraclehour_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; chat_obj=update.effective_chat
    try:
        mem=await context.bot.get_chat_member(chat_obj.id,u.id)
        if mem.status not in ("administrator","creator"):
            await update.message.reply_text("👁️ Admins only."); return
    except: pass
    if await _rexists(f"ev_active:{chat_obj.id}"):
        await update.message.reply_text("⚡ Event active! Type /enter"); return
    ev=random.choice(_EVS)
    await _rsetex(f"ev_active:{chat_obj.id}",150,"1")
    await _rsetex(f"ev_data:{chat_obj.id}",150,json.dumps(ev))
    await _rdel(f"ev_ents:{chat_obj.id}")
    await update.message.reply_text(
        f"{ev['name']}\n\nFirst *{ev['slots']}* to type `/enter` win `{ev['reward']}` coins!\n⏳ 2 minutes only!",parse_mode=ParseMode.MARKDOWN)
    async def close(ctx):
        await _rdel(f"ev_active:{chat_obj.id}",f"ev_data:{chat_obj.id}",f"ev_ents:{chat_obj.id}")
        await ctx.bot.send_message(chat_obj.id,f"🌑 *{ev['name']}* has ended.\n_Watch for the next sign..._ 👁️",parse_mode=ParseMode.MARKDOWN)
    context.job_queue.run_once(close,120,name=f"ev_{chat_obj.id}")

async def enter_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; chat_obj=update.effective_chat
    if not await _rexists(f"ev_active:{chat_obj.id}"):
        await update.message.reply_text("🌑 No active event right now."); return
    raw=await _rget(f"ev_data:{chat_obj.id}")
    if not raw: return
    ev=json.loads(raw); ents=await _rlrange(f"ev_ents:{chat_obj.id}",0,-1)
    if str(u.id) in (ents or []):
        await update.message.reply_text("👁️ You're already in!"); return
    if len(ents or [])>=ev["slots"]:
        await update.message.reply_text("💀 All spots taken!"); return
    await _rlpush(f"ev_ents:{chat_obj.id}",str(u.id)); await _rexpire(f"ev_ents:{chat_obj.id}",180)
    await _addcoins(u.id,ev["reward"])
    pos=len(ents or [])+1; medals=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"]
    await update.message.reply_text(
        f"{medals[pos-1] if pos<=len(medals) else '✅'} *{u.first_name} entered!*\n🪙 `+{ev['reward']}` coins\n"
        f"{'⏳ '+str(ev['slots']-pos)+' spots left' if ev['slots']-pos>0 else '🔒 Event Full!'}",parse_mode=ParseMode.MARKDOWN)

async def eventcheck_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    chat_obj=update.effective_chat
    if not await _rexists(f"ev_active:{chat_obj.id}"):
        await update.message.reply_text("🌑 No active event.\n_Watch for the Oracle's signal..._"); return
    raw=await _rget(f"ev_data:{chat_obj.id}")
    if not raw: return
    ev=json.loads(raw); ents=await _rlrange(f"ev_ents:{chat_obj.id}",0,-1)
    await update.message.reply_text(f"⚡ *EVENT ACTIVE*\n{ev['name']}\n👥 `{len(ents or [])}/{ev['slots']}`\n\n_Type /enter to claim!_",parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════════════
# MINES GAME
# ══════════════════════════════════════════════════════════════════════════
_MDIFFS={"easy":3,"medium":5,"hard":8,"insane":12}

def _mmult(gems,mines):
    if gems==0: return 1.0
    m=1.0; rs=16-mines; rt=16
    for _ in range(gems):
        if rt<=0 or rs<=0: break
        m*=(rt/rs)*0.97; rs-=1; rt-=1
    return round(m,2)

def _mkbd(g):
    grid=g["grid"]; rev=g["revealed"]; done=g.get("done",False); rows=[]
    for r in range(4):
        row=[]
        for c in range(4):
            i=r*4+c
            if i in rev: lbl="💣" if grid[i]=="mine" else "💎"; cb=f"mn_no:{i}"
            elif done: lbl="💣" if grid[i]=="mine" else "·"; cb=f"mn_no:{i}"
            else: lbl="⬛"; cb=f"mn_pick:{i}"
            row.append(InlineKeyboardButton(lbl,callback_data=cb))
        rows.append(row)
    if not done and len(rev)>0:
        m=_mmult(len(rev),g["mines"]); w=int(g["bet"]*m)
        rows.append([InlineKeyboardButton(f"💰 Cash Out — {w} coins ({m}x)",callback_data="mn_cash")])
    return InlineKeyboardMarkup(rows)

def _mtxt(g):
    gems=len(g["revealed"]); bet=g["bet"]; mines=g["mines"]; m=_mmult(gems,mines); nm=g["name"]
    if g.get("lost"): return f"💣 *MINE HIT — GAME OVER*\n👤 {nm}\nBet: `{bet}` | Lost: `{bet}` coins\n_The Oracle warned you about greed..._"
    if g.get("cashed"): return f"💰 *CASHED OUT!*\n👤 {nm}\nGems: `{gems}` | `{m}x`\nWon: `{int(bet*m)}` coins ✨"
    return f"💣 *MINES*\n👤 {nm} | Bet: `{bet}`\n💎 Gems: `{gems}` | 📈 `{m}x`\n💵 Potential: `{int(bet*m)}` coins\n_Pick a tile or cash out_ 🌙"

async def mines_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user
    if await _rexists(f"mines:{u.id}"): await update.message.reply_text("⚠️ Finish your current game first!"); return
    if not context.args:
        await update.message.reply_text("💣 *MINES*\nUsage: `/mines <bet> <easy|medium|hard|insane>`\nExample: `/mines 500 medium`",parse_mode=ParseMode.MARKDOWN); return
    try: bet=int(context.args[0].lower().replace("k","000"))
    except: await update.message.reply_text("❌ Invalid bet."); return
    if bet<10: await update.message.reply_text("❌ Min bet: 10 coins."); return
    diff=context.args[1].lower() if len(context.args)>1 else "medium"
    if diff not in _MDIFFS: await update.message.reply_text("❌ Difficulty: easy/medium/hard/insane"); return
    bal=await _coins(u.id)
    if bal<bet: await update.message.reply_text(f"💸 Not enough coins! Balance: `{bal}`",parse_mode=ParseMode.MARKDOWN); return
    await _addcoins(u.id,-bet)
    mc=_MDIFFS[diff]; grid=["gem"]*16
    for p in random.sample(range(16),mc): grid[p]="mine"
    g={"uid":u.id,"name":u.first_name,"bet":bet,"mines":mc,"grid":grid,"revealed":[],"done":False,"lost":False,"cashed":False}
    await _rsetex(f"mines:{u.id}",600,json.dumps(g))
    msg=await update.message.reply_text(_mtxt(g),reply_markup=_mkbd(g),parse_mode=ParseMode.MARKDOWN)
    g["mid"]=msg.message_id; await _rsetex(f"mines:{u.id}",600,json.dumps(g))

async def mines_cb(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; u=q.from_user; await q.answer()
    raw=await _rget(f"mines:{u.id}")
    if not raw: await q.answer("⏰ Game expired!",show_alert=True); return
    g=json.loads(raw)
    if g["uid"]!=u.id: await q.answer("❌ Not your game!",show_alert=True); return
    d=q.data
    if d.startswith("mn_no"): return
    if d=="mn_cash":
        if len(g["revealed"])==0: await q.answer("Pick at least one gem first!",show_alert=True); return
        m=_mmult(len(g["revealed"]),g["mines"]); w=int(g["bet"]*m)
        g["cashed"]=True; g["done"]=True; await _addcoins(u.id,w); await _rdel(f"mines:{u.id}")
        try: await q.edit_message_text(_mtxt(g),reply_markup=_mkbd(g),parse_mode=ParseMode.MARKDOWN)
        except: pass; return
    if d.startswith("mn_pick:"):
        i=int(d.split(":")[1])
        if i in g["revealed"]: return
        if g["grid"][i]=="mine":
            g["lost"]=True; g["done"]=True; g["revealed"].append(i); await _rdel(f"mines:{u.id}")
        else:
            g["revealed"].append(i)
            safe=16-g["mines"]
            if len(g["revealed"])>=safe:
                m=_mmult(len(g["revealed"]),g["mines"]); w=int(g["bet"]*m)
                g["cashed"]=True; g["done"]=True; await _addcoins(u.id,w); await _rdel(f"mines:{u.id}")
            else: await _rsetex(f"mines:{u.id}",600,json.dumps(g))
        try: await q.edit_message_text(_mtxt(g),reply_markup=_mkbd(g),parse_mode=ParseMode.MARKDOWN)
        except: pass

# ══════════════════════════════════════════════════════════════════════════
# SOLO BET — /bet + bbet text trigger
# ══════════════════════════════════════════════════════════════════════════
def _pbet(raw):
    raw=raw.strip().lower()
    if raw in("all","max"): return -1
    if "+" in raw and not raw.startswith("+"):
        p=raw.split("+")
        try: return int(float(p[0])*(10**int(p[1])))
        except: return None
    if raw.endswith("k"):
        try: return int(float(raw[:-1])*1000)
        except: return None
    try: return int(float(raw))
    except: return None

_BW=["🌙 *FORTUNE FAVORS THE FAITHFUL*","✨ *MIDNIGHT LUCK IS REAL*","🔱 *THE STARS ALIGNED*","💰 *THE ORACLE SMILED UPON YOU*"]
_BL=["💀 *THE ORACLE TAKES WHAT IS OWED*","🌑 *THE VOID CLAIMED YOUR COINS*","😭 *EVEN THE STARS MAKE MISTAKES*","🌊 *THE SHADOW WINS THIS ROUND*"]

async def _dobet(update:Update,context:ContextTypes.DEFAULT_TYPE,raw:str):
    u=update.effective_user; m=update.message
    if await _rexists(f"bet_cd:{u.id}"): await m.reply_text("⏳ Wait 3 seconds between bets."); return
    today=date.today().isoformat(); cnt=int(await _rget(f"bet_cnt:{u.id}:{today}") or 0)
    if cnt>=200: await m.reply_text("📊 Daily bet limit (200) reached. Come back tomorrow."); return
    amt=_pbet(raw)
    if amt is None: await m.reply_text("❌ Invalid amount. Try: `bet 500` `bet 5k` `bet 5+3` `bet all`",parse_mode=ParseMode.MARKDOWN); return
    bal=await _coins(u.id)
    if amt==-1: amt=bal
    if amt<=0: await m.reply_text("❌ Must be positive."); return
    if amt>bal: await m.reply_text(f"💸 Not enough! Balance: `{bal}`",parse_mode=ParseMode.MARKDOWN); return
    await _rsetex(f"bet_cd:{u.id}",3,"1"); await _rsetex(f"bet_cnt:{u.id}:{today}",86400,str(cnt+1))
    won=random.random()<0.50
    if won: await _addcoins(u.id,amt); nb=bal+amt
    else: await _addcoins(u.id,-amt); nb=max(0,bal-amt)
    streak=int(await _rget(f"bstreak:{u.id}") or 0)
    streak=streak+1 if won else 0; await _rset(f"bstreak:{u.id}",str(streak))
    hdr=random.choice(_BW if won else _BL)
    res=f"📈 Won: `+{amt:,}`" if won else f"📉 Lost: `-{amt:,}`"
    txt=f"{hdr}\n\n👤 {u.first_name}\n🎲 Bet: `{amt:,}`\n{res}\n💰 Balance: `{nb:,}`"
    if won and streak>=2: txt+=f"\n🔥 Win streak: `{streak}`"
    await m.reply_text(txt,parse_mode=ParseMode.MARKDOWN)

async def bet_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not context.args:
        u=update.effective_user; bal=await _coins(u.id)
        await update.message.reply_text(f"🎲 *SOLO BET*\nUsage: `/bet <amount>`\nShorthand: `5k`=5000, `5+3`=5000, `all`=full balance\n\n💰 Balance: `{bal:,}`",parse_mode=ParseMode.MARKDOWN); return
    await _dobet(update,context,context.args[0])

async def betstats_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; t=update.message.reply_to_message.from_user if update.message.reply_to_message else u
    w2=int(await _rget(f"bet_wins:{t.id}") or 0); l2=int(await _rget(f"bet_losses:{t.id}") or 0)
    tot=w2+l2; wr=round(w2/tot*100,1) if tot>0 else 0; s2=int(await _rget(f"bstreak:{t.id}") or 0); bal=await _coins(t.id)
    await update.message.reply_text(f"📊 *BET STATS — {t.first_name}*\n💰 Balance: `{bal:,}`\n✅ Wins: `{w2}` | ❌ Losses: `{l2}`\n📈 Win Rate: `{wr}%`\n🔥 Streak: `{s2}`",parse_mode=ParseMode.MARKDOWN)

async def topbet_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    try: keys=await _rkeys("bet_wins:*")
    except: await update.message.reply_text("⚠️ Unavailable."); return
    lb=[]
    for k in (keys or []):
        uid=int(k.split(":")[1]); w2=int(await _rget(k) or 0)
        if w2>0: lb.append((uid,w2))
    lb.sort(key=lambda x:x[1],reverse=True); medals=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]; lines=[]
    for i,(uid,w2) in enumerate(lb[:10]):
        try: mem=await context.bot.get_chat(uid); nm=mem.first_name or "???"
        except: nm="Shadow"
        lines.append(f"{medals[i]} `{nm}` — {w2} wins")
    await update.message.reply_text(f"🎲 *TOP BETTORS*\n\n"+"\n".join(lines)+"\n\n_/bet to join 🌙_",parse_mode=ParseMode.MARKDOWN)

async def bbet_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    m=update.message
    if not m or not m.text: return
    match=re.match(r'(?i)^bbet\s+(\S+)',m.text.strip())
    if not match: return
    await _dobet(update,context,match.group(1))

# ══════════════════════════════════════════════════════════════════════════
# WALLET / VAULT
# ══════════════════════════════════════════════════════════════════════════
async def wallet_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; c2=await _coins(u.id); w2=await _wallet(u.id)
    tot=c2+w2; cap=int(tot*0.30); pct=round(w2/cap*100,1) if cap>0 else 0
    bar="█"*min(10,int(w2/cap*10) if cap>0 else 0)+"░"*(10-min(10,int(w2/cap*10) if cap>0 else 0))
    await update.message.reply_text(f"🏦 *VAULT — {u.first_name}*\n💰 Coins: `{c2:,}`\n🔐 Vault: `{w2:,}`\nCapacity: `{w2}/{cap}` ({pct}%)\n`{bar}`\n\n_/deposit and /withdraw to manage_\n_Vault coins cannot be robbed_ 🛡️",parse_mode=ParseMode.MARKDOWN)

async def deposit_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; c2=await _coins(u.id); w2=await _wallet(u.id)
    cap=int((c2+w2)*0.30); space=cap-w2
    if not context.args: await update.message.reply_text(f"🔒 `/deposit <amount>`\nVault space: `{space}` coins",parse_mode=ParseMode.MARKDOWN); return
    raw=context.args[0].lower()
    if raw=="all": amt=min(c2,space)
    else:
        try: amt=int(raw.replace("k","000"))
        except: await update.message.reply_text("❌ Invalid amount."); return
    if space<=0: await update.message.reply_text("🔐 Vault is full!"); return
    amt=min(amt,space,c2)
    if amt<=0: await update.message.reply_text("❌ Nothing to deposit."); return
    await _setcoins(u.id,c2-amt); await _setwallet(u.id,w2+amt)
    await update.message.reply_text(f"🔒 Deposited `{amt:,}` coins.\n💰 Coins: `{c2-amt:,}` | 🔐 Vault: `{w2+amt:,}`",parse_mode=ParseMode.MARKDOWN)

async def withdraw_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; c2=await _coins(u.id); w2=await _wallet(u.id)
    if not context.args: await update.message.reply_text(f"🔓 `/withdraw <amount>`\nVault: `{w2:,}` coins",parse_mode=ParseMode.MARKDOWN); return
    raw=context.args[0].lower()
    if raw=="all": amt=w2
    else:
        try: amt=int(raw.replace("k","000"))
        except: await update.message.reply_text("❌ Invalid amount."); return
    if amt>w2: await update.message.reply_text(f"❌ Vault only has `{w2:,}` coins.",parse_mode=ParseMode.MARKDOWN); return
    await _setwallet(u.id,w2-amt); await _setcoins(u.id,c2+amt)
    await update.message.reply_text(f"🔓 Withdrew `{amt:,}` coins.\n💰 Coins: `{c2+amt:,}` | 🔐 Vault: `{w2-amt:,}`",parse_mode=ParseMode.MARKDOWN)

async def setpass_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type!="private": await update.message.reply_text("🔐 Use this in my DMs only!"); return
    u=update.effective_user
    if not context.args: await update.message.reply_text("🔐 `/setpass <password>` — protects your account",parse_mode=ParseMode.MARKDOWN); return
    pw=context.args[0]
    if len(pw)<6: await update.message.reply_text("❌ Min 6 characters."); return
    if await _rexists(f"apass:{u.id}"): await update.message.reply_text("⚠️ Already set. Use /changepass."); return
    await _rset(f"apass:{u.id}",hashlib.sha256(pw.encode()).hexdigest())
    try: await update.message.delete()
    except: pass
    await context.bot.send_message(u.id,f"✅ Password set!\nYour ID: `{u.id}` — save this for recovery.",parse_mode=ParseMode.MARKDOWN)

async def changepass_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type!="private": await update.message.reply_text("🔐 DMs only!"); return
    u=update.effective_user
    if not context.args or len(context.args)<2: await update.message.reply_text("Usage: `/changepass <old> <new>`",parse_mode=ParseMode.MARKDOWN); return
    stored=await _rget(f"apass:{u.id}")
    if not stored: await update.message.reply_text("❌ No password set."); return
    if hashlib.sha256(context.args[0].encode()).hexdigest()!=stored: await update.message.reply_text("❌ Wrong password."); return
    await _rset(f"apass:{u.id}",hashlib.sha256(context.args[1].encode()).hexdigest())
    try: await update.message.delete()
    except: pass
    await context.bot.send_message(u.id,"✅ Password changed! 🔐")

async def recover_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type!="private": await update.message.reply_text("🔐 DMs only!"); return
    u=update.effective_user
    if not context.args or len(context.args)<2: await update.message.reply_text("🔐 `/recover <old_user_id> <password>`",parse_mode=ParseMode.MARKDOWN); return
    try: old=int(context.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    if old==u.id: await update.message.reply_text("❌ That's your current ID."); return
    stored=await _rget(f"apass:{old}")
    if not stored or hashlib.sha256(context.args[1].encode()).hexdigest()!=stored:
        await update.message.reply_text("❌ Wrong ID or password."); return
    oc=await _coins(old); ow=await _wallet(old)
    await _addcoins(u.id,oc); await _setwallet(u.id,(await _wallet(u.id))+ow)
    for k in [f"coins:{old}",f"wallet:{old}",f"streak:{old}",f"checkin:{old}",f"apass:{old}"]:
        await _rdel(k)
    try: await update.message.delete()
    except: pass
    await context.bot.send_message(u.id,f"✅ *RECOVERED*\n💰 Coins: `+{oc:,}`\n🔐 Vault: `+{ow:,}`\n\n_Welcome back. The Oracle remembered you._ 🌙",parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════════════
# SMART STICKER SYSTEM v2 — mood-aware sticker replies
# Bot reads message context and picks the RIGHT sticker vibe
# ══════════════════════════════════════════════════════════════════════════

async def smart_sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.sticker: return

    chat_id = update.effective_chat.id
    sticker = message.sticker
    file_id = sticker.file_id

    # Save to pool — separated by emoji category
    emoji = sticker.emoji or "🌙"
    
    # Categorize by emoji mood
    happy_emojis = ["😂","🤣","😊","😄","😁","🥳","🎉","✨","💫","🌟","😍","🥰","💕","❤️","🫶"]
    sad_emojis = ["😭","😢","💔","🥺","😔","😞","😟","🫂","💙"]
    hype_emojis = ["🔥","💪","⚡","🚀","💯","👑","🏆","😤","🤩"]
    dark_emojis = ["💀","☠️","😈","👹","🌑","🖤","👁️","🌙","⚰️"]
    
    if emoji in happy_emojis:
        mood = "happy"
    elif emoji in sad_emojis:
        mood = "sad"
    elif emoji in hype_emojis:
        mood = "hype"
    elif emoji in dark_emojis:
        mood = "dark"
    else:
        mood = "neutral"

    # Save sticker to mood pool
    pool_key = f"stickers:{chat_id}:{mood}"
    pool_raw = await _rget(pool_key)
    pool = json.loads(pool_raw) if pool_raw else []
    if file_id not in pool:
        pool.append(file_id)
        if len(pool) > 30: pool = pool[-30:]
        await _rset(pool_key, json.dumps(pool))

    # Also save to general pool
    gen_key = f"stickers:{chat_id}:neutral"
    gen_raw = await _rget(gen_key)
    gen_pool = json.loads(gen_raw) if gen_raw else []
    if file_id not in gen_pool:
        gen_pool.append(file_id)
        if len(gen_pool) > 50: gen_pool = gen_pool[-50:]
        await _rset(gen_key, json.dumps(gen_pool))

    # 35% chance to reply
    if random.random() > 0.35: return

    await asyncio.sleep(random.uniform(0.8, 2.0))

    # Try to reply with same-mood sticker
    reply_sticker = None
    
    # Try mood pool first
    if pool and len(pool) >= 2:
        choices = [s for s in pool if s != file_id]
        if choices:
            reply_sticker = random.choice(choices)
    
    # Fall back to general pool
    if not reply_sticker and gen_pool and len(gen_pool) >= 2:
        choices = [s for s in gen_pool if s != file_id]
        if choices:
            reply_sticker = random.choice(choices)
    
    # Last resort — echo back
    if not reply_sticker:
        reply_sticker = file_id

    try:
        await message.reply_sticker(reply_sticker)
        logger.info(f"[Sticker] Replied with mood={mood} sticker in {chat_id}")
    except Exception as e:
        logger.warning(f"[Sticker] Failed: {e}")
        # Text fallback based on mood
        fallbacks = {
            "happy": ["😂", "✨", "🖤"],
            "sad": ["🫂", "🌙", "💙"],
            "hype": ["🔥", "💯", "⚡"],
            "dark": ["👁️", "💀", "🌑"],
            "neutral": ["🌙", "✨", "🖤"]
        }
        try:
            await message.reply_text(random.choice(fallbacks.get(mood, ["🌙"])))
        except: pass



# ══════════════════════════════════════════════════════════════════════════
# ACTION COMMANDS — hug, slap, kiss, pat, poke, cuddle, bite, highfive
# These use GIF-style text art + Oracle personality
# ══════════════════════════════════════════════════════════════════════════

_ACTIONS = {
    "hug": {
        "emoji": "🤗",
        "texts": [
            "{from} pulled {to} into a hug so warm even the Oracle felt it 🌙",
            "{from} wrapped {to} in a hug. the void approved. 🖤",
            "a {from}-shaped warmth just reached {to} ✨",
            "{to} has been hugged by {from}. resistance is futile 🤗",
        ]
    },
    "slap": {
        "emoji": "👋",
        "texts": [
            "{from} slapped {to} with the force of a thousand unsent texts 💀",
            "the Oracle watched {from} slap {to} and said nothing. balance. 👋",
            "{to} got slapped by {from}. deserved? the Oracle does not judge. 🌙",
            "*SMACK* — {from} → {to}. the stars witnessed this. ✨",
        ]
    },
    "kiss": {
        "emoji": "💋",
        "texts": [
            "{from} kissed {to}. the Oracle felt second-hand butterflies 💋",
            "bold move, {from}. {to} didn't see that coming 👀",
            "{from} → {to} 💋 the midnight hour notes this officially.",
            "the Oracle registers: {from} kissed {to}. filed. 🖤",
        ]
    },
    "pat": {
        "emoji": "🥺",
        "texts": [
            "{from} gently patted {to} on the head 🥺 the Oracle approves.",
            "soft pat from {from} to {to}. heal, little soul. 🌙",
            "{to} has been patted by {from}. you are seen. ✨",
            "{from} said 'you're okay' without words. just a pat. for {to}. 🖤",
        ]
    },
    "poke": {
        "emoji": "👉",
        "texts": [
            "{from} poked {to} 👉 hey. HEY. pay attention.",
            "*poke* — {from} to {to}. the Oracle witnessed this juvenile act 💀",
            "{to} has been poked by {from}. respond or forever be poked. 👀",
            "{from}: 👉 {to}: 👈 the oracle sees the chaos unfolding.",
        ]
    },
    "cuddle": {
        "emoji": "🫂",
        "texts": [
            "{from} curled up next to {to}. the Oracle dims the lights 🌙",
            "cuddling detected: {from} + {to}. the night just got warmer 🖤",
            "{from} chose {to} for cuddle hours. valid. extremely valid. 🫂",
            "the Oracle blesses this cuddle. {from} + {to} = ✨",
        ]
    },
    "bite": {
        "emoji": "😈",
        "texts": [
            "{from} bit {to}. the Oracle didn't stop it. interesting. 😈",
            "feral moment: {from} → {to}. noted. 💀",
            "{to} has been bitten by {from}. you are claimed now apparently 🖤",
            "{from} bit {to} and the midnight hour said 'yeah okay' 🌙",
        ]
    },
    "highfive": {
        "emoji": "🙌",
        "texts": [
            "{from} high-fived {to}! the Oracle claps once. slowly. 🙌",
            "energy transfer: {from} → {to}. go get it. ✨",
            "{from} + {to} = unstoppable. the Oracle confirms this. 💫",
            "high five locked in. {from} and {to} are now a unit. 🖤",
        ]
    },
    "wave": {
        "emoji": "👋",
        "texts": [
            "{from} waved at {to} 👋 the Oracle notes the acknowledgment.",
            "gentle wave from {from} to {to}. you are seen. 🌙",
            "{to}! {from} is waving at you 👋 respond, don't ghost.",
            "across the void, {from} waved. {to} felt it. ✨",
        ]
    },
    "tickle": {
        "emoji": "😂",
        "texts": [
            "{from} tickled {to} and the Oracle had to look away from the chaos 😂",
            "TICKLE ATTACK: {from} → {to}. the group erupts. 💀",
            "{to} is being tickled by {from}. someone stop this. 🌙",
            "{from} found {to}'s weakness. it was tickles. it's always tickles. ✨",
        ]
    },
}

async def _action_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    u = update.effective_user
    info = _ACTIONS.get(action)
    if not info: return

    # Get target
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
        to_name = f"*{target.first_name}*"
    elif context.args:
        to_name = f"*{' '.join(context.args)}*"
    else:
        await update.message.reply_text(
            f"{info['emoji']} Reply to someone or tag them: `/{action} @username`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    from_name = f"*{u.first_name}*"
    text = random.choice(info["texts"]).replace("{from}", from_name).replace("{to}", to_name)
    await update.message.reply_text(f"{info['emoji']} {text}", parse_mode=ParseMode.MARKDOWN)

# Individual action handlers
async def hug_cmd(u, c): await _action_command(u, c, "hug")
async def slap_cmd(u, c): await _action_command(u, c, "slap")
async def kiss_cmd(u, c): await _action_command(u, c, "kiss")
async def pat_cmd(u, c): await _action_command(u, c, "pat")
async def poke_cmd(u, c): await _action_command(u, c, "poke")
async def cuddle_cmd(u, c): await _action_command(u, c, "cuddle")
async def bite_cmd(u, c): await _action_command(u, c, "bite")
async def highfive_cmd(u, c): await _action_command(u, c, "highfive")
async def wave_cmd(u, c): await _action_command(u, c, "wave")
async def tickle_cmd(u, c): await _action_command(u, c, "tickle")


# ══════════════════════════════════════════════════════════════════════════
# MINI GAMES — fun, fast, group-friendly
# ══════════════════════════════════════════════════════════════════════════

# ── FAST MATHS — first to answer wins coins ──────────────────────────────
async def fastmath_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if await _rexists(f"fastmath:{chat_id}"):
        await update.message.reply_text("⚡ A math round is already active! Answer it first.")
        return

    a = random.randint(10, 99)
    b = random.randint(10, 99)
    op = random.choice(["+", "-", "×"])
    if op == "+": ans = a + b
    elif op == "-": ans = a - b
    else: ans = a * b; op = "×"

    reward = random.randint(50, 150)
    await _rsetex(f"fastmath:{chat_id}", 30, json.dumps({"ans": ans, "reward": reward}))

    await update.message.reply_text(
        f"⚡ *FAST MATHS*\n\n`{a} {op} {b} = ?`\n\n"
        f"🪙 First correct answer wins `{reward}` coins!\n_You have 30 seconds_ ⏳",
        parse_mode=ParseMode.MARKDOWN
    )

async def fastmath_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listens to all messages for fast math answers"""
    chat_id = update.effective_chat.id
    raw = await _rget(f"fastmath:{chat_id}")
    if not raw: return

    data = json.loads(raw)
    text = (update.message.text or "").strip()

    try:
        user_ans = int(text)
    except:
        return  # not a number, ignore

    if user_ans == data["ans"]:
        await _rdel(f"fastmath:{chat_id}")
        u = update.effective_user
        reward = data["reward"]
        await _addcoins(u.id, reward)
        await update.message.reply_text(
            f"✅ *{u.first_name} got it!*\n\nAnswer: `{data['ans']}`\n🪙 `+{reward}` coins!",
            parse_mode=ParseMode.MARKDOWN
        )


# ── WORD BOMB — say a word starting with the last letter ─────────────────
async def wordbomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user

    if await _rexists(f"wordbomb:{chat_id}"):
        await update.message.reply_text("💣 Word bomb already running! Keep the chain going.")
        return

    starters = ["midnight","oracle","shadow","cosmic","mystic","dream","ghost","flame","storm","void"]
    word = random.choice(starters)
    await _rsetex(f"wordbomb:{chat_id}", 300, json.dumps({
        "last_word": word, "last_uid": u.id, "used": [word], "count": 0
    }))

    await update.message.reply_text(
        f"💣 *WORD BOMB*\n\nStart: *{word.upper()}*\n\n"
        f"Next word must start with: *{word[-1].upper()}*\n"
        f"_Reply with a valid word — no repeats — 5 min timer_ 🌙",
        parse_mode=ParseMode.MARKDOWN
    )

async def wordbomb_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    raw = await _rget(f"wordbomb:{chat_id}")
    if not raw: return

    data = json.loads(raw)
    u = update.effective_user
    text = (update.message.text or "").strip().lower()

    # Must be a single word
    if " " in text or not text.isalpha(): return

    # Must start with correct letter
    required_start = data["last_word"][-1]
    if not text.startswith(required_start): return

    # Must not be repeated
    if text in data["used"]:
        await update.message.reply_text(f"❌ *{text}* already used! 💀", parse_mode=ParseMode.MARKDOWN)
        return

    # Same person can't go twice in a row
    if u.id == data["last_uid"]:
        return

    # Valid! Update game
    reward = 10
    await _addcoins(u.id, reward)
    data["used"].append(text)
    data["last_word"] = text
    data["last_uid"] = u.id
    data["count"] += 1
    await _rsetex(f"wordbomb:{chat_id}", 300, json.dumps(data))

    next_letter = text[-1].upper()
    await update.message.reply_text(
        f"✅ *{text.upper()}* — {u.first_name} +{reward}🪙\nNext: *{next_letter}*",
        parse_mode=ParseMode.MARKDOWN
    )


# ── MYSTERY BOX — spend coins, get random reward or nothing ──────────────
_MBOX_OUTCOMES = [
    (0.35, "empty", "💀 *EMPTY BOX*\nThe Oracle laughs softly. Nothing inside."),
    (0.30, "small", "🪙 *SMALL WIN*\nThe shadows gave you something small."),
    (0.20, "medium", "✨ *NICE WIN*\nThe oracle smiles upon you."),
    (0.10, "big", "🔱 *BIG WIN*\nThe stars aligned for a moment."),
    (0.05, "jackpot", "💎 *JACKPOT*\n👁️ THE ORACLE IS SHOOK. HOW."),
]

async def mysterybox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    cost = 100  # costs 100 coins to open

    if await _rexists(f"mbox_cd:{u.id}"):
        ttl = await _rttl(f"mbox_cd:{u.id}")
        await update.message.reply_text(
            f"🎁 Box recharges in `{ttl//60}m {ttl%60}s` 🌙",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    bal = await _coins(u.id)
    if bal < cost:
        await update.message.reply_text(
            f"💸 Need `{cost}` coins to open a Mystery Box.\nYou have `{bal}`. Try /checkin first.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await _addcoins(u.id, -cost)
    await _rsetex(f"mbox_cd:{u.id}", 3600, "1")

    # Pick outcome
    roll = random.random()
    cumulative = 0
    outcome_type = "empty"
    for prob, otype, _ in _MBOX_OUTCOMES:
        cumulative += prob
        if roll < cumulative:
            outcome_type = otype
            break

    # Calculate reward
    multipliers = {"empty": 0, "small": random.uniform(0.5, 1.5),
                   "medium": random.uniform(2, 4), "big": random.uniform(5, 10),
                   "jackpot": random.uniform(15, 25)}
    won = int(cost * multipliers[outcome_type])

    msg = next(m for p, t, m in _MBOX_OUTCOMES if t == outcome_type)

    if won > 0:
        await _addcoins(u.id, won)
        result_text = f"{msg}\n\n👤 {u.first_name}\n💸 Spent: `{cost}` | Won: `+{won}`\n💰 Net: `+{won-cost}`"
    else:
        result_text = f"{msg}\n\n👤 {u.first_name}\n💸 Lost: `{cost}` coins\n_Better luck next hour._ 🌑"

    await update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN)


# ── ORACLE DUEL — two people bet against each other ──────────────────────
async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text("⚔️ Reply to someone's message to challenge them: `/duel <amount>`", parse_mode=ParseMode.MARKDOWN)
        return

    t = update.message.reply_to_message.from_user
    if t.id == u.id or t.is_bot:
        await update.message.reply_text("❌ Can't duel yourself or a bot.")
        return

    if not context.args:
        await update.message.reply_text("⚔️ `/duel <amount>` — reply to challenge someone", parse_mode=ParseMode.MARKDOWN)
        return

    try: amt = int(context.args[0].replace("k","000"))
    except: await update.message.reply_text("❌ Invalid amount."); return

    if amt < 50:
        await update.message.reply_text("❌ Minimum duel: 50 coins.")
        return

    u_bal = await _coins(u.id)
    t_bal = await _coins(t.id)

    if u_bal < amt:
        await update.message.reply_text(f"💸 You only have `{u_bal}` coins.", parse_mode=ParseMode.MARKDOWN)
        return
    if t_bal < amt:
        await update.message.reply_text(f"💸 {t.first_name} only has `{t_bal}` coins.", parse_mode=ParseMode.MARKDOWN)
        return

    # Instant duel — coin flip with Oracle drama
    await asyncio.sleep(1.5)
    winner = random.choice([u, t])
    loser = t if winner.id == u.id else u

    await _addcoins(winner.id, amt)
    await _addcoins(loser.id, -amt)

    dramas = [
        f"⚔️ *ORACLE DUEL*\n\n{u.first_name} vs {t.first_name}\nBet: `{amt}` coins\n\n👑 *{winner.first_name} WINS*\n`+{amt}` coins\n\n_The Oracle has spoken._ 🌙",
        f"⚔️ *MIDNIGHT DUEL*\n\n{u.first_name} ⚔️ {t.first_name}\nStakes: `{amt}` 🪙\n\n💀 {loser.first_name} falls.\n✨ *{winner.first_name} rises.*\n\n_Destiny is not random. Or is it?_ 👁️",
        f"⚔️ *DUEL COMPLETE*\n\nThe Oracle watched closely.\n\n🏆 *{winner.first_name}* — `+{amt}` coins\n💀 *{loser.first_name}* — `-{amt}` coins\n\n_Balance restored._ 🖤",
    ]
    await update.message.reply_text(random.choice(dramas), parse_mode=ParseMode.MARKDOWN)


# ── CONFESSION — anonymous confession to the group ───────────────────────
async def confess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not context.args:
        await update.message.reply_text("🤫 `/confess <your confession>` — posted anonymously", parse_mode=ParseMode.MARKDOWN)
        return

    if await _rexists(f"confess_cd:{u.id}"):
        ttl = await _rttl(f"confess_cd:{u.id}")
        await update.message.reply_text(f"🌑 Wait `{ttl//60}m` before confessing again.", parse_mode=ParseMode.MARKDOWN)
        return

    await _rsetex(f"confess_cd:{u.id}", 21600, "1")
    confession = " ".join(context.args)

    try: await update.message.delete()
    except: pass

    openers = [
        "someone in this group needed to say this",
        "a soul confessed to the Oracle tonight",
        "the midnight hour carries a secret",
        "the Oracle was asked to deliver this",
    ]

    await context.bot.send_message(
        update.effective_chat.id,
        f"🤫 *ANONYMOUS CONFESSION*\n_...{random.choice(openers)}..._\n\n❝ {confession} ❞\n\n👁️ _The Oracle keeps their name in the shadows._",
        parse_mode=ParseMode.MARKDOWN
    )


# ── RANKING GAME — Oracle ranks members chaotically ─────────────────────
_RANK_CATEGORIES = [
    "most likely to disappear for 3 days and come back saying 'was busy'",
    "most likely to be a main character in their own movie",
    "most dangerous when bored",
    "most likely to reply with a meme when you're being serious",
    "the group therapist who definitely needs therapy",
    "most likely to start drama accidentally",
    "the one who holds everything together silently",
    "most likely to ghost someone and feel bad about it for months",
    "most chaotic energy in the group",
    "the one who shows up late to everything and makes it better",
]

async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user

    # Try to get recent chat members from message history — use sender
    category = random.choice(_RANK_CATEGORIES)

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
        await update.message.reply_text(
            f"👑 *ORACLE RANKS*\n\n*{target.first_name}* is...\n\n_{category}_\n\n🌙 _The Oracle has decided. This is final._",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"👑 *ORACLE RANK OF THE MOMENT*\n\n*{u.first_name}* is...\n\n_{category}_\n\n🌙 _Reply to someone to rank them instead._",
            parse_mode=ParseMode.MARKDOWN
        )



# ══════════════════════════════════════════════════════════════════════════
# BOT ALIVE SYSTEM — bot initiates, not just responds
# Tracks activity, notices silence, starts things on its own
# ══════════════════════════════════════════════════════════════════════════

# Track last message time per chat
_last_msg_time = {}
_last_bot_initiate = {}

# What the bot says when group goes quiet (dead for 2+ hours)
_REVIVAL_MSGS = [
    "koi hai? 👀 ya sab so gaye",
    "yaar group itna quiet kyun hai aaj 🌙",
    "the oracle senses... silence. uncomfortable silence. 👁️",
    "group mein kuch toh bol yaar, akela feel ho raha hai 💀",
    "ek kaam karo — /fastmath khelke group zinda karo ⚡",
    "🌑 *crickets* 🌑",
    "koi bata toh — kya chal raha hai sabki life mein? 👀",
    "the void called. it said the group is too quiet. 🖤",
    "yaar kahin gaye ho sab? oracle wait kar raha hai ✨",
    "2 baje jaag rahe ho? confess karo /confess se 🤫",
    "ek game khelo na — /wordbomb type karo, oracle wait kar raha hai 💣",
    "aaj ka vibe kya hai sab ka? oracle genuinely curious hai 🌙",
]

# What bot says randomly to spark conversation (when group is active)
_RANDOM_SPARKS = [
    "btw — agar koi sach bolunga toh sunoge? 👁️",
    "the oracle randomly wants to know — sabka aaj ka mood kaisa hai",
    "koi ek cheez batao jo aaj achi lagi ✨",
    "random thought: who in this group has the most secrets? 🌑",
    "yaar honestly — group ka best moment kya tha abhi tak? 🖤",
    "oracle declares it's /vibecheck time 👀",
    "arey koi /mysterybox try karo na, aaj jackpot aane wala hai 🎁",
    "the oracle is bored. start something. /truth kisi ko do. 😈",
    "midnight confession time — /confess se kuch toh daalo 🤫",
    "jo pehle /checkin karega aaj, uska aura strongest hoga 🌙",
]

async def track_group_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on every message — tracks when group was last active"""
    if not update.message: return
    chat_id = update.effective_chat.id
    _last_msg_time[chat_id] = datetime.now()

async def maybe_revive_or_spark(context: ContextTypes.DEFAULT_TYPE):
    """Job that runs every 30 minutes — checks all known chats"""
    now = datetime.now()

    for chat_id, last_time in list(_last_msg_time.items()):
        # Don't initiate too frequently
        last_bot = _last_bot_initiate.get(chat_id)
        if last_bot and (now - last_bot).total_seconds() < 3600:
            continue  # bot already said something in last hour

        silence_mins = (now - last_time).total_seconds() / 60

        # Group dead for 2-6 hours → revival message
        if 120 <= silence_mins <= 360:
            # 40% chance to say something
            if random.random() < 0.40:
                msg = random.choice(_REVIVAL_MSGS)
                try:
                    await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                    _last_bot_initiate[chat_id] = now
                    logger.info(f"[Alive] Revival message sent to {chat_id}")
                except Exception as e:
                    logger.warning(f"[Alive] Revival failed for {chat_id}: {e}")

        # Group active (messaged in last 30 min) → random spark 15% chance
        elif silence_mins < 30:
            if random.random() < 0.15:
                msg = random.choice(_RANDOM_SPARKS)
                try:
                    await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                    _last_bot_initiate[chat_id] = now
                    logger.info(f"[Alive] Spark sent to {chat_id}")
                except Exception as e:
                    logger.warning(f"[Alive] Spark failed for {chat_id}: {e}")

async def auto_start_game(context: ContextTypes.DEFAULT_TYPE):
    """Every 4 hours — if group is active but no game running, start one"""
    now = datetime.now()

    for chat_id, last_time in list(_last_msg_time.items()):
        silence_mins = (now - last_time).total_seconds() / 60

        # Only if group was active in last 2 hours
        if silence_mins > 120:
            continue

        # Don't start if game already running
        if await _rexists(f"fastmath:{chat_id}") or await _rexists(f"wordbomb:{chat_id}"):
            continue

        # 30% chance to auto-start a game
        if random.random() < 0.30:
            game = random.choice(["fastmath", "wordbomb"])

            if game == "fastmath":
                a = random.randint(10, 99)
                b = random.randint(10, 99)
                op = random.choice(["+", "-", "×"])
                if op == "+": ans = a + b
                elif op == "-": ans = a - b
                else: ans = a * b; op = "×"
                reward = random.randint(75, 200)
                await _rsetex(f"fastmath:{chat_id}", 30, json.dumps({"ans": ans, "reward": reward}))
                openers = [
                    f"👀 achha koi batao —\n\n⚡ `{a} {op} {b} = ?`\n\n🪙 pehla sahi jawab = `{reward}` coins",
                    f"oracle bored hai, game khelte hain —\n\n⚡ *`{a} {op} {b}`* = ?\n\n`{reward}` coins pehle sahi wale ko 🌙",
                    f"⚡ sudden math attack:\n\n`{a} {op} {b} = ?`\n\nfast bolo, {reward} coins milenge 💀",
                ]
                try:
                    await context.bot.send_message(chat_id, random.choice(openers), parse_mode=ParseMode.MARKDOWN)
                    logger.info(f"[AutoGame] fastmath started in {chat_id}")
                except Exception as e:
                    logger.warning(f"[AutoGame] failed: {e}")

            elif game == "wordbomb":
                starters = ["midnight","oracle","shadow","cosmic","mystic","dream","ghost","flame","storm","void","dark","luna","echo","vibe","soul"]
                word = random.choice(starters)
                await _rsetex(f"wordbomb:{chat_id}", 300, json.dumps({
                    "last_word": word, "last_uid": 0, "used": [word], "count": 0
                }))
                openers = [
                    f"💣 khelenge? word bomb —\n\nstart: *{word.upper()}*\nNext letter: *{word[-1].upper()}*\n_ek word bolo jo {word[-1].upper()} se shuru ho_",
                    f"oracle ne word bomb shuru kiya —\n\n*{word.upper()}* → aage tum\n_{word[-1].upper()} se koi word bolo_ 💣",
                    f"💣 *WORD BOMB*\n\n{word.upper()} → next: *{word[-1].upper()}*\n_chain mat todna_ 🌙",
                ]
                try:
                    await context.bot.send_message(chat_id, random.choice(openers), parse_mode=ParseMode.MARKDOWN)
                    logger.info(f"[AutoGame] wordbomb started in {chat_id}")
                except Exception as e:
                    logger.warning(f"[AutoGame] failed: {e}")



# ══════════════════════════════════════════════════════════════════════════
# SECRET COUPLES GAME — 24 hour secret pairing system
# ══════════════════════════════════════════════════════════════════════════

# Storage keys:
# couple_active:{chat_id}         → "1" if game running
# couple_pool:{chat_id}           → JSON list of {uid, name} who joined
# couple_pairs:{chat_id}          → JSON dict {uid: {partner_uid, partner_name, missions_done}}
# couple_notified:{chat_id}:{uid} → "1" if DM sent
# couple_mission:{chat_id}:{uid}  → current mission text

_COUPLE_MISSIONS = [
    "Send your partner a voice note saying something nice about them — without revealing who you are 🌙",
    "Tag your partner in a reel or meme that reminds you of them — but don't say why 👀",
    "Text your partner: 'I know your secret' and see how they react 😈",
    "React to every single message your partner sends today with an emoji only 🔮",
    "Send your partner an anonymous compliment through the Oracle using /vent 🖤",
    "Start a conversation with your partner in the group without them knowing it's you ✨",
    "Send your partner 3 words that describe them — anonymously via /vent 👁️",
    "React to your partner's next message with 🖤 and ghost them after 💀",
    "Quote one of your partner's old messages and reply to it today 🌙",
    "Defend your partner if anyone jokes about them today — secretly 🛡️",
]

_COUPLE_REVEALS = [
    "🌙 *THE ORACLE REVEALS ALL*\n\n24 hours have passed. The shadows lift.\nYour secret pair was...",
    "👁️ *MIDNIGHT CONFESSION*\n\nThe Oracle kept your secret. Now it speaks.\nThe hidden pairs were...",
    "🖤 *THE VEIL LIFTS*\n\n24 hours of secrets. Now the truth.\nThe Oracle paired...",
    "✨ *COSMIC REVEAL*\n\nThe stars witnessed everything.\nYour secret couple was...",
]

_COUPLE_OPENERS = [
    "🌙 *A SECRET GAME BEGINS*\n\nThe Oracle is pairing souls in the shadows.\nType /joincouple to enter the pool.\nPairing happens in *10 minutes* — no one will know who got paired with whom. 👁️",
    "💀 *MIDNIGHT PAIRING — SECRET EDITION*\n\nThe Oracle will secretly pair everyone who types /joincouple.\nYou have *10 minutes*.\nYour partner will be a mystery. For 24 hours. 🌙",
    "🖤 *THE ORACLE PLAYS MATCHMAKER*\n\nSecret couples. 24 hours. Nobody knows who's paired.\nType /joincouple if you dare.\n*10 minutes to join.* ✨",
    "👁️ *SHADOW PAIRING INITIATED*\n\nThe Oracle is watching. And pairing.\nType /joincouple — you'll get a secret partner for 24 hours.\nNo one will know. Not even them. 🌑",
]

async def startcouple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user

    if await _rexists(f"couple_active:{chat_id}"):
        await update.message.reply_text("👁️ A pairing is already active! Wait for it to end or check /couplestatus")
        return

    # Mark game as collecting
    await _rsetex(f"couple_active:{chat_id}", 86400 + 600, "collecting")
    await _rdel(f"couple_pool:{chat_id}")

    opener = random.choice(_COUPLE_OPENERS)
    await update.message.reply_text(opener, parse_mode=ParseMode.MARKDOWN)

    # Auto-pair after 10 minutes
    context.job_queue.run_once(
        _do_pairing,
        600,
        data={"chat_id": chat_id},
        name=f"couple_pair_{chat_id}"
    )

    # Schedule reveal after 24 hours
    context.job_queue.run_once(
        _do_reveal,
        86400,
        data={"chat_id": chat_id, "bot": context.bot},
        name=f"couple_reveal_{chat_id}"
    )

async def joincouple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user

    status = await _rget(f"couple_active:{chat_id}")
    if not status:
        await update.message.reply_text("🌑 No active pairing right now. Wait for someone to start one with /startcouple")
        return
    if status != "collecting":
        await update.message.reply_text("👁️ Pairing already happened! You joined too late this time 💀")
        return

    # Check if already joined
    raw = await _rget(f"couple_pool:{chat_id}")
    pool = json.loads(raw) if raw else []
    if any(p["uid"] == u.id for p in pool):
        await update.message.reply_text(f"✨ {u.first_name}, you're already in the pool. The Oracle sees you. 👁️")
        return

    pool.append({"uid": u.id, "name": u.first_name})
    await _rset(f"couple_pool:{chat_id}", json.dumps(pool))

    # Delete their message for secrecy
    try: await update.message.delete()
    except: pass

    # Confirm privately in group (vague)
    confirmations = [
        f"👁️ *someone* joined the pool... 🌙",
        f"✨ the Oracle felt a new presence enter the shadows...",
        f"🖤 *a soul stepped forward.* the Oracle noted it.",
        f"🌑 someone dared to join. bold. 👀",
    ]
    await context.bot.send_message(chat_id, random.choice(confirmations), parse_mode=ParseMode.MARKDOWN)

    # Send DM confirmation
    try:
        await context.bot.send_message(
            u.id,
            f"🌙 *You're in, {u.first_name}.*\n\nThe Oracle received you.\nYour secret partner will be revealed to you alone — in exactly 10 minutes.\n\n_Don't tell anyone you joined. That's part of the game._ 👁️",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass  # They haven't started bot — that's okay

async def _do_pairing(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]

    raw = await _rget(f"couple_pool:{chat_id}")
    pool = json.loads(raw) if raw else []

    if len(pool) < 2:
        await _rdel(f"couple_active:{chat_id}", f"couple_pool:{chat_id}")
        await context.bot.send_message(
            chat_id,
            "🌑 Not enough souls entered the pool. The Oracle sleeps.\n_Try /startcouple again when more people are around._",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Shuffle and pair
    random.shuffle(pool)
    pairs = {}

    # If odd number, last person gets paired with random from already paired
    for i in range(0, len(pool) - 1, 2):
        a = pool[i]
        b = pool[i + 1]
        pairs[str(a["uid"])] = {"partner_uid": b["uid"], "partner_name": b["name"], "missions_done": 0}
        pairs[str(b["uid"])] = {"partner_uid": a["uid"], "partner_name": a["name"], "missions_done": 0}

    # Handle odd one out
    if len(pool) % 2 == 1:
        lone = pool[-1]
        random_partner = random.choice(pool[:-1])
        pairs[str(lone["uid"])] = {"partner_uid": random_partner["uid"], "partner_name": random_partner["name"], "missions_done": 0}

    await _rset(f"couple_pairs:{chat_id}", json.dumps(pairs))
    await _rset(f"couple_active:{chat_id}", "paired")

    # Send DMs to each person
    for uid_str, info in pairs.items():
        uid = int(uid_str)
        partner_name = info["partner_name"]
        mission = random.choice(_COUPLE_MISSIONS)
        await _rset(f"couple_mission:{chat_id}:{uid}", mission)

        try:
            await context.bot.send_message(
                uid,
                f"👁️ *THE ORACLE SPEAKS — FOR YOUR EYES ONLY*\n\n"
                f"Your secret partner for the next 24 hours is...\n\n"
                f"*{partner_name}* 🖤\n\n"
                f"━━━━━━━━━━━━\n"
                f"🕯️ *Your secret mission:*\n_{mission}_\n"
                f"━━━━━━━━━━━━\n\n"
                f"_Do not reveal who your partner is. The Oracle is watching._\n"
                f"_In 24 hours, all will be revealed in the group._ 🌙",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"Could not DM uid {uid}: {e}")

    # Announce in group (vague, no names)
    pair_count = len(pairs) // 2
    announcements = [
        f"🌙 *THE ORACLE HAS PAIRED {pair_count} COUPLES*\n\nThey know who they are.\nYou don't.\n\n_24 hours. Then the truth._ 👁️",
        f"👁️ *SECRET PAIRINGS COMPLETE*\n\n{pair_count} couples now exist in the shadows.\nEach one knows their partner.\nYou don't know theirs.\n\n_The reveal happens in 24 hours._ 🖤",
        f"✨ *{pair_count} SOULS HAVE BEEN PAIRED*\n\nThe Oracle sent everyone a secret DM.\nWatch the group carefully.\nSomething is happening beneath the surface.\n\n_24 hours until the truth._ 🌑",
    ]
    await context.bot.send_message(chat_id, random.choice(announcements), parse_mode=ParseMode.MARKDOWN)

async def _do_reveal(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]

    raw = await _rget(f"couple_pairs:{chat_id}")
    if not raw:
        return
    pairs = json.loads(raw)

    # Build reveal message — only show each pair once
    seen = set()
    lines = []
    for uid_str, info in pairs.items():
        uid = int(uid_str)
        partner_uid = info["partner_uid"]
        pair_key = tuple(sorted([uid, partner_uid]))
        if pair_key in seen:
            continue
        seen.add(pair_key)

        # Get names
        try:
            a_chat = await context.bot.get_chat(uid)
            a_name = a_chat.first_name or "Mystery Soul"
        except:
            a_name = "Mystery Soul"
        try:
            b_chat = await context.bot.get_chat(partner_uid)
            b_name = b_chat.first_name or "Mystery Soul"
        except:
            b_name = "Mystery Soul"

        lines.append(f"💞 *{a_name}* & *{b_name}*")

    reveal_header = random.choice(_COUPLE_REVEALS)
    reveal_text = reveal_header + "\n\n" + "\n".join(lines) + "\n\n_The Oracle kept your secret for 24 hours.\nNow the shadows lift. 🌙_"

    await context.bot.send_message(chat_id, reveal_text, parse_mode=ParseMode.MARKDOWN)

    # Cleanup
    await _rdel(
        f"couple_active:{chat_id}",
        f"couple_pool:{chat_id}",
        f"couple_pairs:{chat_id}"
    )

async def couplestatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user
    status = await _rget(f"couple_active:{chat_id}")

    if not status:
        await update.message.reply_text("🌑 No active couples game right now.\n_Type /startcouple to begin one._ 🌙", parse_mode=ParseMode.MARKDOWN)
        return

    if status == "collecting":
        raw = await _rget(f"couple_pool:{chat_id}")
        pool = json.loads(raw) if raw else []
        await update.message.reply_text(
            f"👁️ *PAIRING IN PROGRESS*\n\n"
            f"Souls in pool: `{len(pool)}`\n"
            f"_Type /joincouple before time runs out!_ 🌙",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if status == "paired":
        # Tell the user their partner privately — only if they DM the bot
        if update.effective_chat.type == "private":
            raw = await _rget(f"couple_pairs:{chat_id}")
            # Can't check without knowing the group — just give generic
            await update.message.reply_text(
                "👁️ The Oracle remembers your pairing.\nCheck your DM from when the game started. 🌙",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"🌙 *SECRET COUPLES ACTIVE*\n\nPairs exist. Secrets are kept.\n_Reveal happens in 24 hours._ 👁️\n\n_The Oracle says nothing more._",
                parse_mode=ParseMode.MARKDOWN
            )

async def mymission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM command — user can check their mission"""
    u = update.effective_user
    if update.effective_chat.type != "private":
        await update.message.reply_text("👁️ Use this in my DMs — secrets stay secret.")
        return

    # We don't know which group they're in — check all couple_mission keys
    keys = await _rkeys(f"couple_mission:*:{u.id}")
    if not keys:
        await update.message.reply_text("🌑 You don't have an active mission right now.\nJoin a couples game with /joincouple first!")
        return

    mission = await _rget(keys[0])
    await update.message.reply_text(
        f"🕯️ *YOUR SECRET MISSION*\n\n_{mission}_\n\n_Complete it before the reveal. The Oracle is watching._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )



# ══════════════════════════════════════════════════════════════════════════
# WEEKLY SUMMARY JOB
# ══════════════════════════════════════════════════════════════════════════
async def weekly_summary(context:ContextTypes.DEFAULT_TYPE):
    cid=context.job.data.get("chat_id")
    if not cid: return
    try: keys=await _rkeys("coins:*")
    except: return
    lb=[]
    for k in (keys or []):
        uid=int(k.split(":")[1]); c2=await _coins(uid)
        if c2>0: lb.append((uid,c2))
    lb.sort(key=lambda x:x[1],reverse=True); medals=["🥇","🥈","🥉"]; lines=[]
    for i,(uid,c2) in enumerate(lb[:3]):
        try: mem=await context.bot.get_chat(uid); nm=mem.first_name or "???"
        except: nm="Shadow"
        lines.append(f"{medals[i]} {nm} — `{c2:,}` 🪙")
    moods=["Chaotic Neutral","Eerily Calm","Collectively Unhinged","Surprisingly Wholesome","Dangerously Inspired"]
    await context.bot.send_message(cid,
        f"📊 *MIDNIGHT ORACLE — WEEKLY REPORT*\n_{datetime.now().strftime('%d %B %Y')}_\n\n"
        f"🏆 *Top Holders:*\n"+"\n".join(lines)+f"\n\n🌙 Group Mood: _{random.choice(moods)}_\n_/checkin daily · /coinboard for full rankings_ 👁️",
        parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════════════
# COMMAND MENU
# ══════════════════════════════════════════════════════════════════════════
BOT_COMMANDS=[
    # ── oracle ──
    BotCommand("oracle",        "🔮 today's prophecy"),
    BotCommand("aura",          "🌈 your aura reading"),
    BotCommand("vibecheck",     "✨ vibe check"),
    BotCommand("identity",      "🃏 oracle identity card"),
    BotCommand("shadow",        "🌑 your shadow self"),
    BotCommand("element",       "🌌 your cosmic element"),
    BotCommand("corecode",      "🔱 your core personality"),
    BotCommand("duality",       "☯️ your light & dark side"),
    BotCommand("nightreport",   "🌙 tonight's energy reading"),
    BotCommand("sigil",         "✦ your personal sigil"),
    BotCommand("universe",      "💫 universe speaks to you"),
    BotCommand("ritual",        "🕯️ today's ritual"),
    BotCommand("glitch",        "⚡ oracle glitches out"),

    # ── coins & economy ──
    BotCommand("checkin",       "🌙 daily check-in + streak"),
    BotCommand("balance",       "💰 your coin balance"),
    BotCommand("daily",         "🪙 claim daily coins"),
    BotCommand("coinboard",     "🏆 coin leaderboard"),
    BotCommand("cgift",         "💝 gift coins — reply to use"),
    BotCommand("rob",           "🦹 rob someone — reply to use"),
    BotCommand("wallet",        "🏦 your safe vault"),
    BotCommand("deposit",       "🔒 lock coins in vault"),
    BotCommand("withdraw",      "🔓 take coins from vault"),

    # ── games ──
    BotCommand("bet",           "🎲 50/50 bet"),
    BotCommand("mines",         "💣 mines game"),
    BotCommand("duel",          "⚔️ challenge someone — reply to use"),
    BotCommand("mysterybox",    "🎁 open a mystery box"),
    BotCommand("fastmath",      "⚡ first to solve wins coins"),
    BotCommand("wordbomb",      "💣 word chain game"),
    BotCommand("rps",           "✊ rock paper scissors"),
    BotCommand("dice",          "🎲 roll a dice"),
    BotCommand("truth",         "😬 truth question"),
    BotCommand("dare",          "😤 dare challenge"),
    BotCommand("wyr",           "🤔 would you rather"),
    BotCommand("8ball",         "🎱 magic 8-ball"),
    BotCommand("roulette",      "💀 russian roulette"),

    # ── social ──
    BotCommand("hug",           "🤗 hug someone"),
    BotCommand("pat",           "🥺 pat someone"),
    BotCommand("slap",          "👋 slap someone"),
    BotCommand("kiss",          "💋 kiss someone"),
    BotCommand("poke",          "👉 poke someone"),
    BotCommand("cuddle",        "🫂 cuddle someone"),
    BotCommand("bite",          "😈 bite someone"),
    BotCommand("wave",          "👋 wave at someone"),
    BotCommand("highfive",      "🙌 high five someone"),
    BotCommand("ship",          "💞 ship two people"),
    BotCommand("rank",          "👑 oracle ranks someone"),
    BotCommand("roast",         "🔥 playful roast"),
    BotCommand("compliment",    "💐 give a compliment"),

    # ── secrets ──
    BotCommand("vent",          "🫀 anonymous vent"),
    BotCommand("confess",       "🤫 anonymous confession"),
    BotCommand("startcouple",   "💞 secret 24hr couples game"),
    BotCommand("joincouple",    "🌙 join the couples pool"),
    BotCommand("mymission",     "🕯️ your secret mission — dm only"),
    BotCommand("crush",         "💘 set a secret crush"),
    BotCommand("secretadmirer", "💌 anonymous dm to someone"),

    # ── connection ──
    BotCommand("marry",         "💍 propose to someone"),
    BotCommand("divorce",       "💔 end a marriage"),
    BotCommand("profile",       "👤 your oracle profile"),
    BotCommand("friendship",    "💫 compatibility score"),
    BotCommand("bestie",        "👯 declare a bestie"),
    BotCommand("duo",           "🤝 your duo name"),

    # ── mod & util ──
    BotCommand("ban",           "🔨 ban — admin only"),
    BotCommand("mute",          "🔇 mute — admin only"),
    BotCommand("warn",          "⚠️ warn — admin only"),
    BotCommand("purge",         "🗑️ delete messages — admin"),
    BotCommand("oraclehour",    "⚡ trigger event — admin"),
    BotCommand("enter",         "🎯 join active event"),
    BotCommand("poll",          "📊 create a poll"),
    BotCommand("afk",           "💤 set yourself afk"),
    BotCommand("start",         "🌙 wake the oracle"),
    BotCommand("help",          "👁️ all commands"),
]

# ══════════════════════════════════════════════════════════════════════════
# STARTUP + MAIN
# ══════════════════════════════════════════════════════════════════════════
async def _post_init(app:Application):
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("✅ Commands registered (%d)",len(BOT_COMMANDS))
    await economy.load_from_storage(); logger.info("✅ Economy loaded")
    await timecapsule.load_and_reschedule(app); logger.info("✅ Capsules rescheduled")
    await chat.load_from_storage(); logger.info("✅ Chat settings loaded")
    await marriage.load_from_storage(); logger.info("✅ Marriage data loaded")
    await deathgames.load_from_storage(); logger.info("✅ Death Games loaded")

def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN not set in Render environment.")
    if not RENDER_EXTERNAL_URL: raise RuntimeError("RENDER_EXTERNAL_URL not set.")

    _start_dummy_server()

    app=Application.builder().token(TOKEN).post_init(_post_init).build()

    # Channel oracle + bbet text trigger (priority group 0)
    app.add_handler(MessageHandler(filters.IS_AUTOMATIC_FORWARD & filters.ChatType.GROUPS,handle_channel_post),group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^bbet\s+\S+"),bbet_handler),group=0)

    # Message tracking (groups 1-6)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,chat.auto_reply),group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,friendship.track_message),group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,utility.check_afk_mentions),group=3)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,chat.maybe_react_to_message),group=4)
    app.add_handler(MessageHandler(filters.Sticker.ALL,chat.sticker_reply),group=5)
    app.add_handler(MessageHandler(filters.ANIMATION,chat.gif_reply),group=6)

    # AI chat (group 7 — lowest priority, catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_ai_message),group=7)

    # General
    app.add_handler(CommandHandler("start",utility.start_welcome))
    app.add_handler(CommandHandler("help",utility.help_command))
    app.add_handler(CommandHandler("chat",chat.toggle_chat))
    app.add_handler(CommandHandler("persona",chat.set_persona))
    app.add_handler(CommandHandler("sticker",chat.send_random_sticker))
    app.add_handler(CommandHandler("getstickerid",chat.get_sticker_id))
    app.add_handler(CommandHandler("gif",chat.send_random_gif))

    # Engagement
    app.add_handler(CommandHandler("checkin",checkin_command))
    app.add_handler(CommandHandler("streakcheck",streakcheck_command))
    app.add_handler(CommandHandler("vent",vent_command))
    app.add_handler(CommandHandler("cgift",cgift_command))
    app.add_handler(CommandHandler("coinboard",coinboard_command))
    app.add_handler(CommandHandler("rob",eng_rob_command))

    # Oracle Events
    app.add_handler(CommandHandler("oraclehour",oraclehour_command))
    app.add_handler(CommandHandler("enter",enter_command))
    app.add_handler(CommandHandler("eventcheck",eventcheck_command))

    # handlers/aesthetic.py commands (using exact function names from that file)
    app.add_handler(CommandHandler("aura",aesthetic.aura_command))
    app.add_handler(CommandHandler("identity",aesthetic.identity_command))
    app.add_handler(CommandHandler("oracle",aesthetic.oracle_command))
    app.add_handler(CommandHandler("vibecheck",aesthetic.vibecheck_command))
    app.add_handler(CommandHandler("shadow",aesthetic.shadow_command))
    app.add_handler(CommandHandler("element",aesthetic.element_command))
    app.add_handler(CommandHandler("corecode",aesthetic.corecode_command))
    app.add_handler(CommandHandler("universe",aesthetic.universe_command))
    app.add_handler(CommandHandler("ritual",aesthetic.ritual_command))
    app.add_handler(CommandHandler("duality",aesthetic.duality_command))
    app.add_handler(CommandHandler("glitch",aesthetic.glitch_command))
    app.add_handler(CommandHandler("nightreport",aesthetic.nightreport_command))
    app.add_handler(CommandHandler("sigil",aesthetic.sigil_command))

    # Mines
    app.add_handler(CommandHandler("mines",mines_command))
    app.add_handler(CallbackQueryHandler(mines_cb,pattern="^mn_"))

    # Solo Bet
    app.add_handler(CommandHandler("bet",bet_command))
    app.add_handler(CommandHandler("betstats",betstats_command))
    app.add_handler(CommandHandler("topbet",topbet_command))

    # Wallet
    app.add_handler(CommandHandler("wallet",wallet_command))
    app.add_handler(CommandHandler("deposit",deposit_command))
    app.add_handler(CommandHandler("withdraw",withdraw_command))
    app.add_handler(CommandHandler("setpass",setpass_command))
    app.add_handler(CommandHandler("changepass",changepass_command))
    app.add_handler(CommandHandler("recover",recover_command))

    # Games
    app.add_handler(CommandHandler("quiz",games.quiz))
    app.add_handler(CommandHandler("truth",games.truth))
    app.add_handler(CommandHandler("dare",games.dare))
    app.add_handler(CommandHandler("wyr",games.would_you_rather))
    app.add_handler(CommandHandler("nhie",games.never_have_i_ever))
    app.add_handler(CommandHandler("rps",games.rock_paper_scissors))
    app.add_handler(CommandHandler("riddle",games.riddle))
    app.add_handler(CommandHandler("riddleanswer",games.riddle_answer))
    app.add_handler(CommandHandler("scramble",games.scramble))
    app.add_handler(CommandHandler("unscramble",games.unscramble))
    app.add_handler(CommandHandler("guess",games.guess_number))
    app.add_handler(CommandHandler("leaderboard",games.leaderboard_cmd))
    app.add_handler(CommandHandler("dice",games.dice_game))
    app.add_handler(CommandHandler("darts",games.darts_game))
    app.add_handler(CommandHandler("basketball",games.basketball_game))
    app.add_handler(CommandHandler("bowling",games.bowling_game))
    app.add_handler(CommandHandler("football",games.football_game))
    app.add_handler(CommandHandler("slot",games.slot_game))
    app.add_handler(CommandHandler("hangman",games.hangman))
    app.add_handler(CommandHandler("hangmanguess",games.hangman_guess))
    app.add_handler(CommandHandler("tictactoe",games.tictactoe))
    app.add_handler(CommandHandler("ttt",games.ttt_move))
    app.add_handler(CommandHandler("wordchain",games.wordchain_start))
    app.add_handler(CommandHandler("chainword",games.chain_word))
    app.add_handler(CommandHandler("trivia",games.trivia_category))
    app.add_handler(CommandHandler("wordle",games.wordle))
    app.add_handler(CommandHandler("wordleguess",games.wordle_guess))

    # Moderation
    app.add_handler(CommandHandler("mute",moderation.mute))
    app.add_handler(CommandHandler("unmute",moderation.unmute))
    app.add_handler(CommandHandler("ban",moderation.ban))
    app.add_handler(CommandHandler("kick",moderation.kick))
    app.add_handler(CommandHandler("warn",moderation.warn))
    app.add_handler(CommandHandler("rules",moderation.show_rules))
    app.add_handler(CommandHandler("warnings",moderation.check_warnings))
    app.add_handler(CommandHandler("clearwarns",moderation.clear_warnings))
    app.add_handler(CommandHandler("pin",moderation.pin))
    app.add_handler(CommandHandler("unpin",moderation.unpin))
    app.add_handler(CommandHandler("purge",moderation.purge))
    app.add_handler(CommandHandler("setrules",moderation.set_rules))
    app.add_handler(CommandHandler("lock",moderation.lock))
    app.add_handler(CommandHandler("unlock",moderation.unlock))

    # Stats
    app.add_handler(CommandHandler("stats",stats.stats))
    app.add_handler(CommandHandler("topactive",stats.top_active))
    app.add_handler(CommandHandler("msgcount",stats.msg_count))

    # Economy
    app.add_handler(CommandHandler("daily",economy.daily))
    app.add_handler(CommandHandler("balance",economy.balance))
    app.add_handler(CommandHandler("gamble",economy.gamble))
    app.add_handler(CommandHandler("richest",economy.economy_leaderboard))

    # Marriage
    app.add_handler(CommandHandler("marry",marriage.marry))
    app.add_handler(CommandHandler("accept",marriage.accept))
    app.add_handler(CommandHandler("divorce",marriage.divorce))
    app.add_handler(CommandHandler("profile",marriage.profile))
    app.add_handler(CommandHandler("work",marriage.work))
    app.add_handler(CommandHandler("chests",marriage.chests))
    app.add_handler(CommandHandler("shop",marriage.shop))
    app.add_handler(CommandHandler("buy",marriage.buy))
    app.add_handler(CommandHandler("inventory",marriage.inventory))
    app.add_handler(CommandHandler("gift",marriage.gift))
    app.add_handler(CommandHandler("settings",marriage.settings))

    # Death Games
    app.add_handler(CommandHandler("survive",deathgames.survive))
    app.add_handler(CommandHandler("revive",deathgames.revive))
    app.add_handler(CommandHandler("deathstatus",deathgames.deathstatus))
    app.add_handler(CommandHandler("roulette",deathgames.roulette))
    app.add_handler(CommandHandler("deathgame",deathgames.deathgame))
    app.add_handler(CommandHandler("joingame",deathgames.joingame))
    app.add_handler(CommandHandler("startround",deathgames.startround))
    app.add_handler(CommandHandler("kill",deathgames.kill))
    app.add_handler(CommandHandler("vote",deathgames.vote))
    app.add_handler(CommandHandler("endgame",deathgames.endgame))

    # Utility
    app.add_handler(CommandHandler("id",utility.get_id))
    app.add_handler(CommandHandler("info",utility.user_info))
    app.add_handler(CommandHandler("remind",utility.remind))
    app.add_handler(CommandHandler("groupinfo",utility.group_info))
    app.add_handler(CommandHandler("afk",utility.set_afk))
    app.add_handler(CommandHandler("report",utility.report))

    # Friendship
    app.add_handler(CommandHandler("bestie",friendship.bestie))
    app.add_handler(CommandHandler("duo",friendship.duo))
    app.add_handler(CommandHandler("friendship",friendship.friendship_score))
    app.add_handler(CommandHandler("tagbestie",friendship.tag_bestie))
    app.add_handler(CommandHandler("squad",friendship.squad))
    app.add_handler(CommandHandler("loyalty",friendship.loyalty))
    app.add_handler(CommandHandler("ship",friendship.ship))
    app.add_handler(CommandHandler("randomship",friendship.random_ship))
    app.add_handler(CommandHandler("matchmaker",friendship.matchmaker))
    app.add_handler(CommandHandler("friendshiptest",friendship.friendship_test))

    # Action commands — Oracle personality versions
    app.add_handler(CommandHandler("hug",hug_cmd))
    app.add_handler(CommandHandler("pat",pat_cmd))
    app.add_handler(CommandHandler("highfive",highfive_cmd))
    app.add_handler(CommandHandler("slap",slap_cmd))
    app.add_handler(CommandHandler("kiss",kiss_cmd))
    app.add_handler(CommandHandler("poke",poke_cmd))
    app.add_handler(CommandHandler("cuddle",cuddle_cmd))
    app.add_handler(CommandHandler("wave",wave_cmd))
    app.add_handler(CommandHandler("bite",bite_cmd))
    app.add_handler(CommandHandler("tickle",tickle_cmd))

    # Mini games
    app.add_handler(CommandHandler("fastmath",fastmath_command))
    app.add_handler(CommandHandler("wordbomb",wordbomb_command))
    app.add_handler(CommandHandler("mysterybox",mysterybox_command))
    app.add_handler(CommandHandler("duel",duel_command))
    app.add_handler(CommandHandler("confess",confess_command))
    app.add_handler(CommandHandler("rank",rank_command))

    # Sticker reply — bot learns from group stickers and replies back
    app.add_handler(MessageHandler(filters.Sticker.ALL, smart_sticker_reply), group=8)

    # Fast math answer listener
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fastmath_answer), group=9)

    # Word bomb listener
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wordbomb_play), group=10)

    # Fun
    app.add_handler(CommandHandler("roast",fun.roast))
    app.add_handler(CommandHandler("compliment",fun.compliment))
    app.add_handler(CommandHandler("8ball",fun.eight_ball))
    app.add_handler(CommandHandler("vibe",fun.vibe))
    app.add_handler(CommandHandler("quote",fun.quote))
    app.add_handler(CommandHandler("poll",fun.poll))
    app.add_handler(CommandHandler("rank",fun.rank))
    app.add_handler(CommandHandler("ratethis",fun.rate_this))
    app.add_handler(CommandHandler("impostor",fun.impostor_start))
    app.add_handler(CommandHandler("revealimpostor",fun.impostor_reveal))

    # Matchmaking
    app.add_handler(CommandHandler("crush",matchmaking.set_crush))
    app.add_handler(CommandHandler("clearcrush",matchmaking.clear_crush))
    app.add_handler(CommandHandler("secretadmirer",matchmaking.secret_admirer))

    # Events/Welcome
    app.add_handler(CommandHandler("setwelcome",events.set_welcome))
    app.add_handler(CommandHandler("setgoodbye",events.set_goodbye))
    app.add_handler(CommandHandler("invite",events.get_invite))
    app.add_handler(CommandHandler("joined",events.show_joined))
    app.add_handler(CommandHandler("left",events.show_left))
    app.add_handler(ChatMemberHandler(events.on_chat_member_update,ChatMemberHandler.CHAT_MEMBER))

    # Time Capsule
    app.add_handler(CommandHandler("timecapsule",timecapsule.timecapsule))
    app.add_handler(CommandHandler("capsules",timecapsule.list_capsules))

    # Secret Couples
    app.add_handler(CommandHandler("startcouple", startcouple_command))
    app.add_handler(CommandHandler("joincouple", joincouple_command))
    app.add_handler(CommandHandler("couplestatus", couplestatus_command))
    app.add_handler(CommandHandler("mymission", mymission_command))

    # Activity tracker — runs on every message (group=11, lowest priority)
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, track_group_activity), group=11)

    # Scheduled jobs
    if GROUP_CHAT_ID:
        app.job_queue.run_daily(weekly_summary,datetime.strptime("21:00","%H:%M").time(),days=(6,),data={"chat_id":GROUP_CHAT_ID},name="weekly")
        logger.info("✅ Weekly summary job registered for chat %d",GROUP_CHAT_ID)

    # Alive system jobs — bot initiates on its own
    app.job_queue.run_repeating(maybe_revive_or_spark, interval=1800, first=1800, name="alive_check")
    app.job_queue.run_repeating(auto_start_game, interval=14400, first=7200, name="auto_game")
    logger.info("✅ Alive system jobs registered")

    # Webhook
    full_url=f"{RENDER_EXTERNAL_URL}/{TOKEN}"
    logger.info("🌙 Midnight Oracle awakening... webhook at %s",full_url)
    app.run_webhook(listen="0.0.0.0",port=PORT,url_path=TOKEN,webhook_url=full_url)

if __name__=="__main__":
    main()
