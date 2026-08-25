

import sys, os, logging, random, asyncio, json, hashlib, re, threading
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── PATH FIX ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    Update, Message, InputFile,
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


# ── Internal AI helpers ────────────────────────────────────────────────────
_bot_username_cache = None

async def _get_bot_username(bot):
    """Return and cache the bot username for the AI reply system."""
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    try:
        me = await bot.get_me()
        _bot_username_cache = me.username or ""
    except Exception as e:
        logger.warning(f"Could not resolve bot username: {e}")
        _bot_username_cache = ""
    return _bot_username_cache

async def _get_fallback_reply(name):
    """Local fallback so AI chat still works when Gemini is unavailable."""
    return random.choice([
        f"hey {name} 👀 kya scene hai?",
        f"yo {name} 🌙 I'm listening.",
        f"ayo {name} — bol, kya chal raha hai? 👁️",
        f"{name} entered the chat. noted. 🖤",
    ])

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
    if won:
        await _addcoins(u.id,amt); nb=bal+amt
        await _rset(f"bet_wins:{u.id}", str(int(await _rget(f"bet_wins:{u.id}") or 0) + 1))
    else:
        await _addcoins(u.id,-amt); nb=max(0,bal-amt)
        await _rset(f"bet_losses:{u.id}", str(int(await _rget(f"bet_losses:{u.id}") or 0) + 1))
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
# ORACLE VERDICTS — bot randomly calls someone out, starts conversation
# ══════════════════════════════════════════════════════════════════════════

_VERDICTS = [
    "👁️ *THE ORACLE HAS DECIDED*\n\n*{name}* is hiding something from this group.\n\n_we're not saying what. but we know._ 🌙",
    "🔮 *ORACLE VERDICT*\n\n*{name}* has been thinking about someone in this group.\n\n_they haven't said it yet._ 🖤",
    "💀 *PUBLIC DECLARATION*\n\nThe Oracle officially declares *{name}* as today's most chaotic energy.\n\n_act accordingly._ 👀",
    "🌑 *THE ORACLE SEES*\n\n*{name}* said something recently they didn't fully mean.\n\n_or maybe they meant it more than they admitted._ ✨",
    "👁️ *MIDNIGHT VERDICT*\n\n*{name}* is the most interesting person in this group right now.\n\n_the oracle doesn't explain why. it just knows._ 🌙",
    "🖤 *ORACLE CALLS IT*\n\n*{name}* has an opinion about someone here they've never said out loud.\n\n_the hot seat is open._ 💀",
    "✨ *COSMIC OBSERVATION*\n\n*{name}* is going through something they're not talking about.\n\n_the group is here. just saying._ 🫂",
    "🌙 *THE ORACLE NOTICED*\n\n*{name}* has been quieter than usual.\n\n_that either means peace or chaos is coming._ 👁️",
    "💫 *VERDICT DELIVERED*\n\n*{name}* would survive a horror movie.\n\n_everyone else? debatable._ 💀",
    "🔱 *ORACLE DECLARES*\n\n*{name}* is the main character energy of this group today.\n\n_act like it._ ✨",
]

# Track recent members who sent messages (for verdicts)
_recent_members = {}  # chat_id -> [(uid, name), ...]

async def track_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track who's been active — used for verdicts and titles"""
    if not update.message or not update.effective_user: return
    chat_id = update.effective_chat.id
    u = update.effective_user
    if u.is_bot: return
    if chat_id not in _recent_members:
        _recent_members[chat_id] = []
    # Keep unique, max 50
    existing = [m for m in _recent_members[chat_id] if m[0] != u.id]
    existing.append((u.id, u.first_name))
    _recent_members[chat_id] = existing[-50:]

async def oracle_verdict(context: ContextTypes.DEFAULT_TYPE):
    """Every 6 hours — randomly picks someone and delivers a verdict"""
    for chat_id, members in list(_recent_members.items()):
        if not members: continue
        if random.random() > 0.50: continue  # 50% chance each cycle

        uid, name = random.choice(members)
        verdict = random.choice(_VERDICTS).replace("{name}", name)

        try:
            await context.bot.send_message(chat_id, verdict, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"[Verdict] Delivered for {name} in {chat_id}")
        except Exception as e:
            logger.warning(f"[Verdict] Failed: {e}")

async def verdict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual verdict — admin or anyone can trigger"""
    chat_id = update.effective_chat.id
    members = _recent_members.get(chat_id, [])

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        t = update.message.reply_to_message.from_user
        name = t.first_name
    elif members:
        uid, name = random.choice(members)
    else:
        name = update.effective_user.first_name

    verdict = random.choice(_VERDICTS).replace("{name}", name)
    await update.message.reply_text(verdict, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════════════════════════
# HOT SEAT — anonymous questions, someone must answer
# ══════════════════════════════════════════════════════════════════════════

_HOTSEAT_QUESTIONS = [
    "who in this group do you trust the most and why?",
    "what's one thing you've never told anyone in this group?",
    "who here do you think has the most secrets?",
    "what's the most unhinged thing you've done recently?",
    "who in this group do you think about randomly?",
    "if you had to pick one person from this group to call at 3am — who?",
    "what's something you pretend not to care about but actually do?",
    "who here has surprised you the most — good or bad?",
    "what would the group be shocked to know about you?",
    "who here do you think is completely different in real life vs online?",
    "what's a thought you've had about someone here that you never said?",
    "if this group had a villain — who and why?",
    "who here would you trust with your phone unlocked?",
    "what's the last lie you told someone in this group?",
]

async def hotseat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if await _rexists(f"hotseat:{chat_id}"):
        await update.message.reply_text("🔥 Someone's already on the hot seat. Let them answer first.")
        return

    # Pick a victim
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
    else:
        members = _recent_members.get(chat_id, [])
        if not members:
            await update.message.reply_text("🌑 No one to put on the hot seat yet. Be more active first.")
            return
        uid, fname = random.choice(members)
        # Create fake user object
        class _FakeUser:
            def __init__(self, i, n): self.id = i; self.first_name = n; self.is_bot = False
        target = _FakeUser(uid, fname)

    question = random.choice(_HOTSEAT_QUESTIONS)
    await _rsetex(f"hotseat:{chat_id}", 300, json.dumps({
        "uid": target.id, "name": target.first_name, "question": question
    }))

    await update.message.reply_text(
        f"🔥 *HOT SEAT*\n\n"
        f"*{target.first_name}* — the Oracle has selected you.\n\n"
        f"The group wants to know:\n\n"
        f"❝ _{question}_ ❞\n\n"
        f"_You have 5 minutes. The group is watching._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )

    async def hotseat_timeout(ctx):
        raw = await _rget(f"hotseat:{chat_id}")
        if raw:
            data = json.loads(raw)
            await _rdel(f"hotseat:{chat_id}")
            await ctx.bot.send_message(
                chat_id,
                f"👁️ *{data['name']}* stayed silent.\n_The Oracle notes this. 🖤_",
                parse_mode=ParseMode.MARKDOWN
            )

    context.job_queue.run_once(hotseat_timeout, 300, name=f"hs_{chat_id}")


# ══════════════════════════════════════════════════════════════════════════
# WEEKLY TITLES — Oracle assigns chaotic titles every Sunday
# ══════════════════════════════════════════════════════════════════════════

_TITLES = [
    "👑 Most Chaotic Energy",
    "🌙 The Midnight Haunter",
    "💀 Professionally Unhinged",
    "🖤 The Silent Destroyer",
    "✨ Unexpected Main Character",
    "👁️ The One Who Sees Everything",
    "🔥 This Week's Walking Red Flag",
    "🫂 The Group's Emotional Support",
    "💫 Most Likely to Start Something",
    "🌑 The Mystery We Still Can't Figure Out",
    "⚡ Chaotic Good Incarnate",
    "🎭 The Actor Nobody Asked For",
]

_MSG_COUNT = {}  # chat_id -> {uid -> count}

async def track_msg_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    if update.effective_user.is_bot: return
    if chat_id not in _MSG_COUNT: _MSG_COUNT[chat_id] = {}
    _MSG_COUNT[chat_id][uid] = _MSG_COUNT[chat_id].get(uid, 0) + 1

async def weekly_titles(context: ContextTypes.DEFAULT_TYPE):
    """Every Sunday — assign titles based on activity"""
    for chat_id, counts in list(_MSG_COUNT.items()):
        if not counts: continue
        members = _recent_members.get(chat_id, [])
        if len(members) < 2: continue

        # Most active
        most_active_uid = max(counts, key=counts.get)
        most_active_name = next((n for u, n in members if u == most_active_uid), "???")

        # Most silent (in members list but low count)
        all_uids = {u for u, _ in members}
        silent_uid = min(all_uids, key=lambda u: counts.get(u, 0))
        silent_name = next((n for u, n in members if u == silent_uid), "???")

        # Random title for random person
        random_person = random.choice(members)

        lines = [
            f"👑 *{most_active_name}* — Most Active This Week",
            f"🌑 *{silent_name}* — The Ghost (where were you??)",
            f"{random.choice(_TITLES)} → *{random_person[1]}*",
        ]

        # Add 1-2 more random titles
        remaining = [m for m in members if m[0] not in [most_active_uid, silent_uid, random_person[0]]]
        random.shuffle(remaining)
        for m in remaining[:2]:
            lines.append(f"{random.choice(_TITLES)} → *{m[1]}*")

        await context.bot.send_message(
            chat_id,
            f"🏆 *MIDNIGHT ORACLE — WEEKLY TITLES*\n\n" + "\n".join(lines) +
            f"\n\n_These are permanent. Until next Sunday._ 👁️",
            parse_mode=ParseMode.MARKDOWN
        )

        # Reset counts
        _MSG_COUNT[chat_id] = {}


# ══════════════════════════════════════════════════════════════════════════
# NIGHT MODE — after 11pm bot becomes softer, more real
# ══════════════════════════════════════════════════════════════════════════

_NIGHT_STARTERS = [
    "jo log raat ko jaag rahe hain — kya chal raha hai actually? 🌙",
    "3 baje wali feelings share karo. no judgment. oracle sunta hai. 🖤",
    "ek baar sach mein bolo — aaj ka din kaisa tha? 👁️",
    "raat ko akela feel hota hai kisi ko? be honest. 🌑",
    "kya chal raha hai dimag mein? oracle genuinely jaanna chahta hai. ✨",
    "late night confession time. koi kuch bolta hai? 🤫",
    "night people — bata do. kya miss kar rahe ho aajkal? 💫",
    "aaj kuch aisa hua jo tum expect nahi kar rahe the? 🌙",
]

_night_mode_active = {}  # chat_id -> bool

async def night_mode_check(context: ContextTypes.DEFAULT_TYPE):
    """Every hour — check if it's night time and send a night starter"""
    hour = datetime.now().hour
    is_night = 23 <= hour or hour <= 3

    for chat_id in list(_recent_members.keys()):
        was_night = _night_mode_active.get(chat_id, False)

        if is_night and not was_night:
            # Just entered night mode
            _night_mode_active[chat_id] = True
            if random.random() < 0.60:
                try:
                    await context.bot.send_message(
                        chat_id,
                        random.choice(_NIGHT_STARTERS),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"[NightMode] Activated for {chat_id}")
                except Exception as e:
                    logger.warning(f"[NightMode] Failed: {e}")
        elif not is_night:
            _night_mode_active[chat_id] = False


# ══════════════════════════════════════════════════════════════════════════
# SILENCE GAME — don't talk for 5 min or lose coins
# ══════════════════════════════════════════════════════════════════════════

async def silence_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if await _rexists(f"silence:{chat_id}"):
        await update.message.reply_text("🌑 Already running. Don't. Say. Anything. 👁️")
        return

    await _rsetex(f"silence:{chat_id}", 300, json.dumps({"started_by": update.effective_user.id}))

    await update.message.reply_text(
        "🌑 *THE SILENCE GAME*\n\n"
        "Nobody talks for *5 minutes.*\n"
        "First person to send a message loses *200 coins.* 💀\n\n"
        "_The Oracle is watching. In silence._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )

    async def silence_end(ctx):
        if await _rexists(f"silence:{chat_id}"):
            await _rdel(f"silence:{chat_id}")
            await ctx.bot.send_message(
                chat_id,
                "✅ *SILENCE SURVIVED*\n\nNobody broke. Impressive. The Oracle is... almost proud. 🖤",
                parse_mode=ParseMode.MARKDOWN
            )
    context.job_queue.run_once(silence_end, 300, name=f"sil_{chat_id}")

async def silence_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks if someone broke the silence"""
    if not update.message: return
    chat_id = update.effective_chat.id
    raw = await _rget(f"silence:{chat_id}")
    if not raw: return

    data = json.loads(raw)
    u = update.effective_user
    if u.is_bot: return
    if u.id == data.get("started_by"): return  # starter is immune

    await _rdel(f"silence:{chat_id}")
    penalty = 200
    bal = await _coins(u.id)
    actual_penalty = min(penalty, bal)
    await _addcoins(u.id, -actual_penalty)

    await update.message.reply_text(
        f"💀 *SILENCE BROKEN*\n\n"
        f"*{u.first_name}* couldn't hold it.\n"
        f"Lost: `{actual_penalty}` coins 🪙\n\n"
        f"_The Oracle is disappointed. And also entertained._ 🌙",
        parse_mode=ParseMode.MARKDOWN
    )


# ══════════════════════════════════════════════════════════════════════════
# CRICKET GAME — prediction + live reactions + simple tournament
# Clean, no glitches, full flow
# ══════════════════════════════════════════════════════════════════════════

# Your Telegram user ID — only you can broadcast
# Set this as env variable OWNER_ID in Render
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ── Premium cricket media ─────────────────────────────────────────────────
# These are original lightweight animations shipped with the bot. On first
# use Telegram stores them and we cache the resulting file_id in Redis, so
# later matches do not repeatedly upload the GIF.
CRICKET_GRAPHICS_ENABLED = os.getenv("CRICKET_GRAPHICS_ENABLED", "1").lower() not in ("0", "false", "no")
CRICKET_GRAPHICS_DIR = os.getenv("CRICKET_GRAPHICS_DIR", os.path.join(_HERE, "cricket_graphics"))

async def _send_cricket_graphic(context, chat_id, kind, caption=None):
    """Send a premium cricket animation, caching its Telegram file_id."""
    if not CRICKET_GRAPHICS_ENABLED:
        return None
    try:
        cache_key = f"cricket:graphic:fileid:{kind}"
        cached = await _rget(cache_key)
        if cached:
            msg = await context.bot.send_animation(chat_id=chat_id, animation=cached, caption=caption)
            return msg

        path = os.path.join(CRICKET_GRAPHICS_DIR, f"{kind}.gif")
        if not os.path.exists(path):
            return None

        with open(path, "rb") as fh:
            msg = await context.bot.send_animation(
                chat_id=chat_id, animation=InputFile(fh), caption=caption
            )
        if getattr(msg, "animation", None) and getattr(msg.animation, "file_id", None):
            await _rset(cache_key, msg.animation.file_id)
        return msg
    except Exception as e:
        # Graphics must NEVER break the actual cricket match.
        logger.warning("[CricketGraphics] %s failed: %s", kind, e)
        return None

# Track all groups the bot is in
_known_groups = set()

async def _persist_known_groups():
    """Persist the complete group registry without replacing old groups."""
    await _rset("known_groups", json.dumps(sorted(_known_groups)))

async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track every group the bot is active in and never drop older groups."""
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        before = len(_known_groups)
        _known_groups.add(int(chat.id))
        if len(_known_groups) != before:
            await _persist_known_groups()

async def track_group_migration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Keep the registry alive when Telegram upgrades a group to a supergroup."""
    msg = update.message
    if not msg or not getattr(msg, "migrate_to_chat_id", None):
        return
    old_id = int(msg.chat.id)
    new_id = int(msg.migrate_to_chat_id)
    _known_groups.discard(old_id)
    _known_groups.add(new_id)
    await _persist_known_groups()
    logger.info("[Groups] Migrated %s -> %s", old_id, new_id)

async def _load_known_groups():
    """Load and preserve the existing Redis group registry on startup."""
    raw = await _rget("known_groups")
    if raw:
        try:
            for gid in json.loads(raw):
                _known_groups.add(int(gid))
        except Exception as e:
            logger.warning("[Groups] Could not load known_groups: %s", e)
    logger.info("[Groups] Preserved %d known group(s)", len(_known_groups))

# ══════════════════════════════════════════════════════════════════════════
# BROADCAST SYSTEM — owner sends one message, goes to all groups
# ══════════════════════════════════════════════════════════════════════════

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Only owner can use this — from DM"""
    u = update.effective_user

    # Check owner
    if u.id != OWNER_ID:
        await update.message.reply_text("👁️ not for you.")
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text("🌙 use this in my DMs only.")
        return

    if not context.args:
        await update.message.reply_text(
            "📡 *BROADCAST*\n\n"
            "Usage: `/broadcast <your message>`\n\n"
            "Message will be sent to all connected groups.\n"
            f"Currently connected: `{len(_known_groups)}` groups",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    msg = " ".join(context.args)
    broadcast_text = (
        f"📡 *MIDNIGHT ORACLE — ANNOUNCEMENT*\n\n"
        f"{msg}\n\n"
        f"— _The Oracle_ 🌙"
    )

    # Load fresh from Redis too
    raw = await _rget("known_groups")
    all_groups = set(_known_groups)
    if raw:
        for gid in json.loads(raw):
            all_groups.add(int(gid))

    sent = 0
    failed = 0
    for chat_id in all_groups:
        try:
            await context.bot.send_message(
                chat_id,
                broadcast_text,
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
            await asyncio.sleep(0.3)  # avoid flood
        except Exception as e:
            failed += 1
            logger.warning(f"[Broadcast] Failed for {chat_id}: {e}")

    await update.message.reply_text(
        f"✅ *BROADCAST DONE*\n\n"
        f"Sent: `{sent}` groups\n"
        f"Failed: `{failed}` groups",
        parse_mode=ParseMode.MARKDOWN
    )

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for broadcast"""
    await broadcast_command(update, context)


# ══════════════════════════════════════════════════════════════════════════
# CRICKET — prediction + live reactions + mini tournament
# ══════════════════════════════════════════════════════════════════════════

_CRICKET_ORACLE_LINES = [
    "🏏 oracle ne dekha — boundaries aane wale hain. tension mat lo.",
    "👁️ wicket. next 3 overs mein. screenshot karo.",
    "🌙 team ki energy aaj off hai. oracle feels it.",
    "💀 is over mein kuch bura hone wala hai. oracle warned you.",
    "✨ ek bada shot aane wala hai. ready raho.",
    "🔮 spinners aaj dominate karenge. pitch bol rahi hai.",
    "🖤 opposition ka plan readable hai. oracle jaanta hai.",
    "⚡ THIS is the moment. oracle ne call kiya. 👀",
    "🌑 run rate pressure mein hai. next 5 overs critical.",
    "💫 partnership yahan toot sakti hai. oracle soch raha hai.",
]

_CRICKET_WIN_REACTIONS = [
    "🏆 CALLED IT. oracle always knows 👁️",
    "🔥 yaar kya match tha. oracle impressed hai.",
    "✨ the stars aligned. and so did the team.",
    "💀 opposition ko pata bhi nahi chala kya hua.",
    "🌙 oracle ne pehle hi bola tha. kisi ne suna nahi.",
]

_CRICKET_LOSS_REACTIONS = [
    "💔 oracle bhi sad hai honestly. yeh nahi hona chahiye tha.",
    "😭 cricket is pain. oracle understands.",
    "🌑 the void is how we feel right now.",
    "💀 kya tha yeh. oracle ne predict kiya tha but still.",
    "🖤 agle match mein. oracle believes.",
]

_CRICKET_DRAMA = [
    "😭 YAAR KYA THA YEH. oracle is deceased 💀",
    "👁️ the oracle watched this and felt something deeply.",
    "🔥 THE ENERGY. THE DRAMA. oracle is HERE for it.",
    "💔 iss wicket ke baad oracle bhi rona chahta hai.",
    "⚡ that shot. THAT SHOT. oracle screaming internally.",
    "🌙 cricket at night hits completely different. oracle confirms.",
    "💀 opponent ne yeh nahi karna chahiye tha. bad idea.",
    "✨ when cricket becomes art. oracle appreciates.",
]

# ── MATCH PREDICTION GAME ─────────────────────────────────────────────────

async def cricket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oracle reacts to cricket naturally"""
    text = " ".join(context.args).lower() if context.args else ""

    if any(w in text for w in ["win","jeet","won","champion"]):
        reply = random.choice(_CRICKET_WIN_REACTIONS)
    elif any(w in text for w in ["loss","haar","lost","out","duck"]):
        reply = random.choice(_CRICKET_LOSS_REACTIONS)
    elif any(w in text for w in ["predict","bol","batao","kaun","who"]):
        reply = random.choice(_CRICKET_ORACLE_LINES)
    else:
        reply = random.choice(_CRICKET_DRAMA)

    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


async def cricket_predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oracle makes a formal prediction — group can bet on it"""
    chat_id = update.effective_chat.id

    if await _rexists(f"cpredict:{chat_id}"):
        raw = await _rget(f"cpredict:{chat_id}")
        data = json.loads(raw)
        await update.message.reply_text(
            f"🔮 *ACTIVE PREDICTION*\n\n_{data['prediction']}_\n\n"
            f"Team A bets: `{data['team_a_count']}`\n"
            f"Team B bets: `{data['team_b_count']}`\n\n"
            f"_/cwin <team> to resolve when match ends_ 👁️",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🏏 `/cpredict <Team A> vs <Team B>`\n"
            "Example: `/cpredict India Pakistan`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    team_a = context.args[0].capitalize()
    team_b = context.args[-1].capitalize()
    prediction = random.choice(_CRICKET_ORACLE_LINES)

    data = {
        "team_a": team_a,
        "team_b": team_b,
        "prediction": prediction,
        "team_a_bets": {},   # uid -> amount
        "team_b_bets": {},
        "team_a_count": 0,
        "team_b_count": 0,
    }
    await _rsetex(f"cpredict:{chat_id}", 86400, json.dumps(data))

    await update.message.reply_text(
        f"🏏 *ORACLE MATCH PREDICTION*\n\n"
        f"*{team_a}* 🆚 *{team_b}*\n\n"
        f"👁️ Oracle says:\n_{prediction}_\n\n"
        f"━━━━━━━━━━━━\n"
        f"Place your bets:\n"
        f"`/cbet {team_a} <amount>` — bet on {team_a}\n"
        f"`/cbet {team_b} <amount>` — bet on {team_b}\n\n"
        f"_When match ends, admin uses /cwin <team>_ 🌙",
        parse_mode=ParseMode.MARKDOWN
    )


async def cricket_bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bet on a team in active prediction"""
    chat_id = update.effective_chat.id
    u = update.effective_user

    if not await _rexists(f"cpredict:{chat_id}"):
        await update.message.reply_text(
            "🌑 No active match prediction.\n"
            "_Start one with /cpredict Team1 Team2_ 🏏",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🏏 `/cbet <team> <amount>`\nExample: `/cbet India 500`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    team = context.args[0].capitalize()
    try:
        amt = int(context.args[1].replace("k", "000"))
    except:
        await update.message.reply_text("❌ Invalid amount.")
        return

    if amt < 50:
        await update.message.reply_text("❌ Minimum bet: 50 coins.")
        return

    raw = await _rget(f"cpredict:{chat_id}")
    data = json.loads(raw)

    team_a = data["team_a"]
    team_b = data["team_b"]

    # Check if valid team
    if team.lower() not in [team_a.lower(), team_b.lower()]:
        await update.message.reply_text(
            f"❌ Bet on *{team_a}* or *{team_b}* only.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check if already bet
    uid_str = str(u.id)
    if uid_str in data["team_a_bets"] or uid_str in data["team_b_bets"]:
        await update.message.reply_text("👁️ You already placed a bet. Wait for the result.")
        return

    bal = await _coins(u.id)
    if bal < amt:
        await update.message.reply_text(f"💸 You only have `{bal}` coins.", parse_mode=ParseMode.MARKDOWN)
        return

    await _addcoins(u.id, -amt)

    # Add bet to correct team
    if team.lower() == team_a.lower():
        data["team_a_bets"][uid_str] = amt
        data["team_a_count"] += 1
        chosen = team_a
    else:
        data["team_b_bets"][uid_str] = amt
        data["team_b_count"] += 1
        chosen = team_b

    await _rsetex(f"cpredict:{chat_id}", 86400, json.dumps(data))

    await update.message.reply_text(
        f"🏏 *BET PLACED*\n\n"
        f"*{u.first_name}* → *{chosen}*\n"
        f"Amount: `{amt}` coins 🪙\n\n"
        f"_Oracle is watching the match._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )


async def cricket_win_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin declares winner — distributes coins"""
    chat_id = update.effective_chat.id
    u = update.effective_user

    # Admin check
    try:
        mem = await context.bot.get_chat_member(chat_id, u.id)
        if mem.status not in ("administrator", "creator"):
            await update.message.reply_text("👁️ Admins only.")
            return
    except:
        pass

    if not await _rexists(f"cpredict:{chat_id}"):
        await update.message.reply_text("🌑 No active match prediction.")
        return

    if not context.args:
        await update.message.reply_text(
            "🏏 `/cwin <winning team>`\nExample: `/cwin India`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    raw = await _rget(f"cpredict:{chat_id}")
    data = json.loads(raw)
    winner_team = context.args[0].capitalize()

    team_a = data["team_a"]
    team_b = data["team_b"]

    if winner_team.lower() not in [team_a.lower(), team_b.lower()]:
        await update.message.reply_text(
            f"❌ Winner must be *{team_a}* or *{team_b}*.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Determine winning and losing bets
    if winner_team.lower() == team_a.lower():
        winning_bets = data["team_a_bets"]
        losing_bets = data["team_b_bets"]
        losing_team = team_b
    else:
        winning_bets = data["team_b_bets"]
        losing_bets = data["team_a_bets"]
        losing_team = team_a

    # Total losing pool distributed to winners
    total_losing = sum(losing_bets.values())
    total_winning = sum(winning_bets.values())

    winners_text = []
    for uid_str, amt in winning_bets.items():
        uid = int(uid_str)
        # Return their bet + proportional share of losing pool
        if total_winning > 0:
            share = int((amt / total_winning) * total_losing)
        else:
            share = 0
        winnings = amt + share
        await _addcoins(uid, winnings)
        try:
            chat_user = await context.bot.get_chat(uid)
            name = chat_user.first_name
        except:
            name = "Shadow"
        winners_text.append(f"💰 *{name}* — `+{share}` profit")

    await _rdel(f"cpredict:{chat_id}")

    result_lines = "\n".join(winners_text) if winners_text else "_no winners this time_"
    reaction = random.choice(_CRICKET_WIN_REACTIONS)

    await update.message.reply_text(
        f"🏆 *{winner_team.upper()} WINS!*\n\n"
        f"{reaction}\n\n"
        f"━━━━━━━━━━━━\n"
        f"*Winners:*\n{result_lines}\n\n"
        f"_Better luck next match, {losing_team} fans._ 🖤",
        parse_mode=ParseMode.MARKDOWN
    )


# ── MINI TOURNAMENT ───────────────────────────────────────────────────────

_IPL_TEAMS = [
    "MI 🔵", "CSK 🟡", "RCB 🔴", "KKR 🟣",
    "DC 🔵", "PBKS 🔴", "RR 🩷", "SRH 🟠",
    "GT 🔵", "LSG 🟡"
]

async def cricket_tournament_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a mini tournament — members pick teams"""
    chat_id = update.effective_chat.id

    if await _rexists(f"ctour:{chat_id}"):
        raw = await _rget(f"ctour:{chat_id}")
        data = json.loads(raw)
        picks = data.get("picks", {})
        lines = [f"*{name}* → {team}" for name, team in picks.items()]
        await update.message.reply_text(
            f"🏏 *TOURNAMENT ACTIVE*\n\n" +
            ("\n".join(lines) if lines else "_no picks yet_") +
            f"\n\n_/cpick <team> to join_\n_/ctourney to see bracket_ 🌙",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await _rsetex(f"ctour:{chat_id}", 604800, json.dumps({
        "picks": {},
        "scores": {},
    }))

    teams_text = "\n".join([f"`{t}`" for t in _IPL_TEAMS])
    await update.message.reply_text(
        f"🏏 *ORACLE MINI TOURNAMENT*\n\n"
        f"Pick your team — use `/cpick <team>`\n\n"
        f"Available:\n{teams_text}\n\n"
        f"_Oracle will run matches. Coins at stake._ 💀",
        parse_mode=ParseMode.MARKDOWN
    )

async def cricket_pick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pick a team in tournament"""
    chat_id = update.effective_chat.id
    u = update.effective_user

    if not await _rexists(f"ctour:{chat_id}"):
        await update.message.reply_text(
            "🌑 No tournament running.\n_/ctournament to start one_ 🏏",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not context.args:
        await update.message.reply_text("🏏 `/cpick <team name>`", parse_mode=ParseMode.MARKDOWN)
        return

    team = " ".join(context.args).upper()
    valid = [t.split()[0] for t in _IPL_TEAMS]

    if team not in valid:
        await update.message.reply_text(
            f"❌ Invalid team. Choose from:\n" +
            ", ".join(f"`{t}`" for t in valid),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    raw = await _rget(f"ctour:{chat_id}")
    data = json.loads(raw)

    # Check if already picked
    if u.first_name in data["picks"]:
        await update.message.reply_text(
            f"👁️ You already picked *{data['picks'][u.first_name]}*.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check if team taken
    if team in data["picks"].values():
        await update.message.reply_text(
            f"❌ *{team}* already taken by someone. Pick another.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    data["picks"][u.first_name] = team
    await _rsetex(f"ctour:{chat_id}", 604800, json.dumps(data))
    await _addcoins(u.id, -100)  # Entry fee

    await update.message.reply_text(
        f"✅ *{u.first_name}* picked *{team}*!\n\n"
        f"Entry fee: `100` coins deducted 🪙\n"
        f"_Oracle is watching your team._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )

async def cricket_play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulate a tournament match — admin triggers"""
    chat_id = update.effective_chat.id
    u = update.effective_user

    try:
        mem = await context.bot.get_chat_member(chat_id, u.id)
        if mem.status not in ("administrator", "creator"):
            await update.message.reply_text("👁️ Admins only.")
            return
    except:
        pass

    if not await _rexists(f"ctour:{chat_id}"):
        await update.message.reply_text("🌑 No tournament running.")
        return

    raw = await _rget(f"ctour:{chat_id}")
    data = json.loads(raw)
    picks = data.get("picks", {})

    if len(picks) < 2:
        await update.message.reply_text("❌ Need at least 2 players to run a match.")
        return

    # Pick two random players
    players = list(picks.items())
    random.shuffle(players)
    p1_name, p1_team = players[0]
    p2_name, p2_team = players[1]

    # Simulate scores
    p1_score = random.randint(120, 220)
    p2_score = random.randint(120, 220)
    while p1_score == p2_score:
        p2_score = random.randint(120, 220)

    winner_name = p1_name if p1_score > p2_score else p2_name
    winner_team = p1_team if p1_score > p2_score else p2_team
    loser_name = p2_name if p1_score > p2_score else p1_name

    # Find winner UID
    members = _recent_members.get(chat_id, [])
    winner_uid = next((uid for uid, name in members if name == winner_name), None)
    if winner_uid:
        await _addcoins(winner_uid, 200)

    await update.message.reply_text(
        f"🏏 *MATCH RESULT*\n\n"
        f"*{p1_name}* ({p1_team}) — `{p1_score}` runs\n"
        f"*{p2_name}* ({p2_team}) — `{p2_score}` runs\n\n"
        f"🏆 *{winner_name}* wins!\n"
        f"🪙 `+200` coins\n\n"
        f"_{random.choice(_CRICKET_DRAMA)}_",
        parse_mode=ParseMode.MARKDOWN
    )




# ══════════════════════════════════════════════════════════════════════════
# CRICKET MATCH ENGINE — true 1v1 bot-run cricket
# A complete short-format match using Telegram inline controls.
#
# Design:
#   • 1v1 member-vs-member
#   • challenge by replying to a member, or open challenge in the group
#   • toss → choose bat/bowl
#   • 2 overs per innings, 2 wickets
#   • every legal ball requires BOTH batter + bowler decisions
#   • six legal balls make an over
#   • chase target and early victory
#   • tied match → Super Over
#   • live scorecard, ball commentary, stats and leaderboard
#   • Redis-backed state with expiry, so it survives bot restarts
#
# The mechanics intentionally follow real cricket concepts such as six-ball
# overs and target chasing, while keeping a Telegram game quick enough to play.
# ══════════════════════════════════════════════════════════════════════════

CRG_PREFIX = "crg:"
CRG_TTL = 7200
CRG_BALL_TIMEOUT = 90
CRG_MAX_OVERS = 2
CRG_WICKETS = 2

_CRG_SHOTS = {
    "defend": "🛡️ Defend",
    "drive": "🏏 Drive",
    "pull": "💥 Pull",
    "sweep": "🌀 Sweep",
    "loft": "🚀 Loft",
    "slog": "🔥 Slog",
}

_CRG_BOWLS = {
    "yorker": "🎯 Yorker",
    "good": "🟢 Good Length",
    "bouncer": "⬆️ Bouncer",
    "slower": "🐢 Slower Ball",
    "spin": "🌀 Spin",
}

_CRG_MATCHUPS = {
    ("drive", "yorker"): {"4": 0.15, "6": 0.03, "2": 0.22, "1": 0.38, "0": 0.18, "W": 0.04},
    ("drive", "good"):   {"4": 0.19, "6": 0.04, "2": 0.22, "1": 0.34, "0": 0.17, "W": 0.04},
    ("drive", "bouncer"):{"4": 0.08, "6": 0.02, "2": 0.15, "1": 0.35, "0": 0.28, "W": 0.12},
    ("drive", "slower"): {"4": 0.14, "6": 0.03, "2": 0.18, "1": 0.34, "0": 0.23, "W": 0.08},
    ("drive", "spin"):   {"4": 0.12, "6": 0.03, "2": 0.24, "1": 0.37, "0": 0.19, "W": 0.05},

    ("defend", "yorker"): {"4": 0.01, "6": 0.00, "2": 0.05, "1": 0.48, "0": 0.43, "W": 0.03},
    ("defend", "good"):   {"4": 0.01, "6": 0.00, "2": 0.06, "1": 0.46, "0": 0.44, "W": 0.03},
    ("defend", "bouncer"):{"4": 0.02, "6": 0.00, "2": 0.08, "1": 0.42, "0": 0.39, "W": 0.09},
    ("defend", "slower"): {"4": 0.02, "6": 0.00, "2": 0.08, "1": 0.44, "0": 0.43, "W": 0.03},
    ("defend", "spin"):   {"4": 0.02, "6": 0.00, "2": 0.10, "1": 0.43, "0": 0.40, "W": 0.05},

    ("pull", "yorker"):   {"4": 0.05, "6": 0.01, "2": 0.12, "1": 0.38, "0": 0.28, "W": 0.16},
    ("pull", "good"):     {"4": 0.12, "6": 0.03, "2": 0.20, "1": 0.36, "0": 0.22, "W": 0.07},
    ("pull", "bouncer"):  {"4": 0.24, "6": 0.07, "2": 0.23, "1": 0.28, "0": 0.13, "W": 0.05},
    ("pull", "slower"):   {"4": 0.15, "6": 0.04, "2": 0.21, "1": 0.33, "0": 0.20, "W": 0.07},
    ("pull", "spin"):     {"4": 0.09, "6": 0.02, "2": 0.18, "1": 0.37, "0": 0.27, "W": 0.07},

    ("sweep", "yorker"):  {"4": 0.06, "6": 0.01, "2": 0.18, "1": 0.39, "0": 0.28, "W": 0.08},
    ("sweep", "good"):    {"4": 0.10, "6": 0.02, "2": 0.20, "1": 0.37, "0": 0.24, "W": 0.07},
    ("sweep", "bouncer"): {"4": 0.04, "6": 0.01, "2": 0.10, "1": 0.34, "0": 0.34, "W": 0.17},
    ("sweep", "slower"):  {"4": 0.08, "6": 0.02, "2": 0.18, "1": 0.38, "0": 0.27, "W": 0.07},
    ("sweep", "spin"):    {"4": 0.22, "6": 0.05, "2": 0.23, "1": 0.31, "0": 0.15, "W": 0.04},

    ("loft", "yorker"):   {"4": 0.14, "6": 0.09, "2": 0.18, "1": 0.22, "0": 0.18, "W": 0.19},
    ("loft", "good"):     {"4": 0.18, "6": 0.12, "2": 0.18, "1": 0.22, "0": 0.13, "W": 0.20},
    ("loft", "bouncer"):  {"4": 0.10, "6": 0.07, "2": 0.12, "1": 0.20, "0": 0.23, "W": 0.28},
    ("loft", "slower"):   {"4": 0.12, "6": 0.07, "2": 0.16, "1": 0.21, "0": 0.18, "W": 0.26},
    ("loft", "spin"):     {"4": 0.20, "6": 0.13, "2": 0.21, "1": 0.22, "0": 0.12, "W": 0.18},

    ("slog", "yorker"):   {"4": 0.10, "6": 0.06, "2": 0.16, "1": 0.25, "0": 0.19, "W": 0.24},
    ("slog", "good"):     {"4": 0.16, "6": 0.10, "2": 0.19, "1": 0.24, "0": 0.13, "W": 0.18},
    ("slog", "bouncer"):  {"4": 0.12, "6": 0.08, "2": 0.14, "1": 0.21, "0": 0.19, "W": 0.26},
    ("slog", "slower"):   {"4": 0.08, "6": 0.05, "2": 0.14, "1": 0.24, "0": 0.19, "W": 0.30},
    ("slog", "spin"):     {"4": 0.19, "6": 0.14, "2": 0.18, "1": 0.23, "0": 0.11, "W": 0.14},
}

_CRG_WICKET_LINES = [
    "💥 GONE! Clean bowled. The stumps are everywhere.",
    "🧤 CAUGHT! The bowler forced the mistake.",
    "🎯 LBW! Huge appeal — finger goes up!",
    "🏃 RUN OUT! Pressure created the wicket.",
]
_CRG_RUN_LINES = {
    0: ["Dot ball. Absolute pressure.", "No run. Bowler wins that battle.", "Beaten! Straight to the field."],
    1: ["Quick single.", "Just one. Keep the scoreboard moving.", "Worked away for a single."],
    2: ["They come back for two!", "Good running — two more.", "Found the gap for a couple."],
    4: ["FOUR! That raced away.", "CRACK! Boundary.", "Timed beautifully — FOUR!"],
    6: ["SIX! Into the night sky!", "MASSIVE! That's six.", "Maximum! What a hit!"],
}

def _crg_key(chat_id):
    return f"{CRG_PREFIX}{chat_id}"

def _crg_stats_key(uid):
    return f"cricket_stats:{uid}"

def _crg_default_stats():
    return {"matches": 0, "wins": 0, "losses": 0, "ties": 0,
            "runs": 0, "wickets": 0, "fours": 0, "sixes": 0}

async def _crg_get(chat_id):
    raw = await _rget(_crg_key(chat_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        await _rdel(_crg_key(chat_id))
        return None

async def _crg_save(chat_id, state):
    await _rsetex(_crg_key(chat_id), CRG_TTL, json.dumps(state, separators=(",", ":")))

def _crg_score(state, uid):
    return state["scores"].get(str(uid), {"runs": 0, "wickets": 0, "balls": 0, "fours": 0, "sixes": 0})

def _crg_name(state, uid):
    p = state["players"].get(str(uid), {})
    return p.get("name", "Player")

def _crg_is_player(state, uid):
    return str(uid) in state.get("players", {})

def _crg_header(state):
    p1, p2 = state["players"].values()
    return f"🏏 {_crg_name(state, p1['uid'])}  vs  {_crg_name(state, p2['uid'])}"

def _crg_scoreline(state):
    parts = []
    for p in state["players"].values():
        s = _crg_score(state, p["uid"])
        parts.append(f"{p['name']}: {s['runs']}/{s['wickets']} ({s['balls']}b)")
    return "  •  ".join(parts)

def _crg_kb_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏏 Join Match", callback_data="crg:join")]
    ])

def _crg_kb_toss(state):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪙 Heads", callback_data="crg:toss:H"),
            InlineKeyboardButton("🪙 Tails", callback_data="crg:toss:T"),
        ]
    ])

def _crg_kb_bat_bowl():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏏 Bat First", callback_data="crg:batfirst"),
            InlineKeyboardButton("🎯 Bowl First", callback_data="crg:bowlfirst"),
        ]
    ])

def _crg_kb_ball(state):
    bat = state["batting_uid"]
    bowl = state["bowling_uid"]
    pending = state.get("pending", {})
    rows = [
        [InlineKeyboardButton(_CRG_SHOTS["defend"], callback_data="crg:shot:defend"),
         InlineKeyboardButton(_CRG_SHOTS["drive"], callback_data="crg:shot:drive")],
        [InlineKeyboardButton(_CRG_SHOTS["pull"], callback_data="crg:shot:pull"),
         InlineKeyboardButton(_CRG_SHOTS["sweep"], callback_data="crg:shot:sweep")],
        [InlineKeyboardButton(_CRG_SHOTS["loft"], callback_data="crg:shot:loft"),
         InlineKeyboardButton(_CRG_SHOTS["slog"], callback_data="crg:shot:slog")],
        [InlineKeyboardButton(_CRG_BOWLS["yorker"], callback_data="crg:bowl:yorker"),
         InlineKeyboardButton(_CRG_BOWLS["good"], callback_data="crg:bowl:good")],
        [InlineKeyboardButton(_CRG_BOWLS["bouncer"], callback_data="crg:bowl:bouncer"),
         InlineKeyboardButton(_CRG_BOWLS["slower"], callback_data="crg:bowl:slower")],
        [InlineKeyboardButton(_CRG_BOWLS["spin"], callback_data="crg:bowl:spin")],
    ]
    # Buttons remain visible to both players; callback validation makes them private in effect.
    return InlineKeyboardMarkup(rows)

def _crg_action_labels(state):
    bat = state["batting_uid"]
    bowl = state["bowling_uid"]
    pending = state.get("pending", {})
    bat_done = str(bat) in pending
    bowl_done = str(bowl) in pending
    return (
        f"🏏 Batter: {'✅ locked' if bat_done else 'choose your shot'}\n"
        f"🎯 Bowler: {'✅ locked' if bowl_done else 'choose your delivery'}"
    )

async def _crg_edit(context, state, text=None, keyboard=None):
    chat_id = state["chat_id"]
    mid = state.get("message_id")
    if not mid:
        return
    if text is None:
        text = _crg_render(state)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=mid, text=text, reply_markup=keyboard
        )
    except Exception as e:
        # Telegram raises when content is unchanged; do not treat that as a game failure.
        if "not modified" not in str(e).lower():
            logger.warning(f"[CricketGame] edit failed: {e}")

def _crg_render(state):
    phase = state["phase"]
    text = f"{_crg_header(state)}\n\n"
    text += f"📊 {_crg_scoreline(state)}\n"
    if phase == "waiting":
        target = state.get("target_uid")
        if target:
            text += f"\n⚔️ Challenge sent to {_crg_name(state, target)}.\nTap Accept to enter."
        else:
            text += "\n👥 Open match — first member to join becomes the opponent."
    elif phase == "toss":
        text += f"\n🪙 Toss time.\n{_crg_name(state, state['toss_uid'])} — choose Heads or Tails."
    elif phase == "choose":
        text += f"\n🏏 Toss won by {_crg_name(state, state['toss_winner'])}.\nChoose whether to bat or bowl first."
    elif phase == "live":
        over = state["legal_balls"] // 6
        ball = state["legal_balls"] % 6
        innings = state["innings"]
        batter = _crg_name(state, state["batting_uid"])
        bowler = _crg_name(state, state["bowling_uid"])
        text += (
            f"\n📍 Innings {innings}  •  Over {over}.{ball}\n"
            f"🏏 Batting: {batter}\n🎯 Bowling: {bowler}\n"
            f"🎯 Target: {state.get('target', '—')}\n\n"
            f"{_crg_action_labels(state)}"
        )
    elif phase == "done":
        text += f"\n\n🏆 {state.get('result', 'Match complete.')}"
    return text

def _crg_weighted_outcome(weights):
    r = random.random()
    acc = 0.0
    for outcome, prob in weights.items():
        acc += prob
        if r <= acc:
            return outcome
    return "0"

def _crg_ball_result(shot, bowl):
    weights = _CRG_MATCHUPS[(shot, bowl)]
    outcome = _crg_weighted_outcome(weights)
    if outcome == "W":
        return {"runs": 0, "wicket": True, "text": random.choice(_CRG_WICKET_LINES)}
    runs = int(outcome)
    return {"runs": runs, "wicket": False, "text": random.choice(_CRG_RUN_LINES[runs])}

async def _crg_start_innings(context, state, innings, batting_uid, bowling_uid, target=None):
    state["phase"] = "live"
    state["innings"] = innings
    state["batting_uid"] = batting_uid
    state["bowling_uid"] = bowling_uid
    state["legal_balls"] = 0
    state["pending"] = {}
    state["target"] = target
    state["last_ball"] = ""
    await _crg_save(state["chat_id"], state)
    await _crg_edit(context, state, _crg_render(state), _crg_kb_ball(state))
    token = state["ball_token"] = hashlib.md5(f"{state['chat_id']}:{innings}:{datetime.now().timestamp()}".encode()).hexdigest()[:12]
    await _crg_save(state["chat_id"], state)
    context.job_queue.run_once(
        _crg_ball_timeout,
        CRG_BALL_TIMEOUT,
        data={"chat_id": state["chat_id"], "token": token},
        name=f"crg_ball_{state['chat_id']}_{token}",
    )

async def _crg_finish_match(context, state, winner_uid=None, tie=False):
    chat_id = state["chat_id"]
    pids = [p["uid"] for p in state["players"].values()]
    if tie:
        state["phase"] = "done"
        state["result"] = "🤝 Match tied. Absolute thriller."
        for uid in pids:
            stats_raw = await _rget(_crg_stats_key(uid))
            st = json.loads(stats_raw) if stats_raw else _crg_default_stats()
            st["matches"] += 1
            st["ties"] += 1
            s = _crg_score(state, uid)
            st["runs"] += s["runs"]; st["wickets"] += s["wickets"]
            st["fours"] += s["fours"]; st["sixes"] += s["sixes"]
            await _rset(_crg_stats_key(uid), json.dumps(st))
    else:
        loser_uid = next(uid for uid in pids if uid != winner_uid)
        state["phase"] = "done"
        win_name = _crg_name(state, winner_uid)
        win_score = _crg_score(state, winner_uid)
        lose_score = _crg_score(state, loser_uid)
        margin = max(1, win_score["runs"] - lose_score["runs"])
        if state.get("innings") == 2 and state.get("target_reached"):
            margin = f"{max(1, CRG_WICKETS - lose_score['wickets'])} wickets"
            margin_text = f"by {margin}"
        else:
            margin_text = f"by {margin} runs"
        state["result"] = f"🏆 {win_name} wins {margin_text}!"
        for uid in pids:
            stats_raw = await _rget(_crg_stats_key(uid))
            st = json.loads(stats_raw) if stats_raw else _crg_default_stats()
            st["matches"] += 1
            if uid == winner_uid:
                st["wins"] += 1
                await _addcoins(uid, 300)
            else:
                st["losses"] += 1
                await _addcoins(uid, 100)
            s = _crg_score(state, uid)
            st["runs"] += s["runs"]; st["wickets"] += s["wickets"]
            st["fours"] += s["fours"]; st["sixes"] += s["sixes"]
            await _rset(_crg_stats_key(uid), json.dumps(st))
    await _crg_save(chat_id, state)
    await _send_cricket_graphic(context, chat_id, "win", caption="🏆 *MATCH COMPLETE*\n_What a game._")
    await _crg_edit(context, state, _crg_render(state), None)

async def _crg_advance_after_innings(context, state):
    # Current innings ended.
    first_bat = state["first_batting_uid"]
    second_bat = state["second_batting_uid"]
    first_score = _crg_score(state, first_bat)["runs"]
    second_score = _crg_score(state, second_bat)["runs"]

    if state["innings"] == 1:
        await _crg_start_innings(
            context, state, 2, second_bat, first_bat, first_score + 1
        )
        return

    # Second innings finished without reaching target.
    if second_score == first_score:
        # Short-format tie -> Super Over.
        state["super_round"] = state.get("super_round", 0) + 1
        state["super_scores"] = {}
        state["first_batting_uid"] = first_bat
        state["second_batting_uid"] = second_bat
        await _crg_start_innings(context, state, 3, first_bat, second_bat, None)
        return

    await _crg_finish_match(context, state, winner_uid=first_bat)

async def _crg_resolve_ball(context, state):
    pending = state.get("pending", {})
    bat = state["batting_uid"]; bowl = state["bowling_uid"]
    shot = pending.get(str(bat))
    delivery = pending.get(str(bowl))
    if not shot or not delivery:
        return

    result = _crg_ball_result(shot, delivery)
    s = _crg_score(state, bat)
    s["balls"] += 1
    if result["wicket"]:
        s["wickets"] += 1
    else:
        s["runs"] += result["runs"]
        if result["runs"] == 4: s["fours"] += 1
        if result["runs"] == 6: s["sixes"] += 1
    state["scores"][str(bat)] = s
    state["legal_balls"] += 1
    state["pending"] = {}
    state["last_ball"] = (
        f"Ball {state['legal_balls']}: {result['text']} "
        f"({shot.title()} vs {delivery.title()})"
    )

    graphic_kind = "wicket" if result["wicket"] else ("six" if result["runs"] == 6 else ("four" if result["runs"] == 4 else None))
    if graphic_kind:
        await _send_cricket_graphic(context, state["chat_id"], graphic_kind)

    target = state.get("target")
    if target and s["runs"] >= target:
        state["target_reached"] = True
        await _crg_finish_match(context, state, winner_uid=bat)
        return

    if s["wickets"] >= CRG_WICKETS or state["legal_balls"] >= CRG_MAX_OVERS * 6:
        if state["innings"] == 3:
            # Super Over winner.
            if state.get("super_first_score") is None:
                state["super_first_score"] = s["runs"]
                # Swap for the reply super over.
                state["super_first_bat"] = bat
                state["super_second_bat"] = bowl
                await _crg_start_innings(context, state, 4, bowl, bat, s["runs"] + 1)
                return
            else:
                if s["runs"] > state["super_first_score"]:
                    await _crg_finish_match(context, state, winner_uid=bat)
                elif s["runs"] < state["super_first_score"]:
                    await _crg_finish_match(context, state, winner_uid=state["super_first_bat"])
                else:
                    # Another Super Over. The first batting side alternates.
                    state["super_first_score"] = None
                    state["super_round"] = state.get("super_round", 0) + 1
                    next_bat = bowl
                    next_bowl = bat
                    await _crg_start_innings(context, state, 3, next_bat, next_bowl, None)
                return

        await _crg_advance_after_innings(context, state)
        return

    # Continue next legal ball.
    await _crg_save(state["chat_id"], state)
    text = _crg_render(state) + f"\n\n💬 {state['last_ball']}"
    await _crg_edit(context, state, text, _crg_kb_ball(state))
    token = hashlib.md5(
        f"{state['chat_id']}:{state['innings']}:{state['legal_balls']}:{datetime.now().timestamp()}".encode()
    ).hexdigest()[:12]
    state["ball_token"] = token
    await _crg_save(state["chat_id"], state)
    context.job_queue.run_once(
        _crg_ball_timeout, CRG_BALL_TIMEOUT,
        data={"chat_id": state["chat_id"], "token": token},
        name=f"crg_ball_{state['chat_id']}_{token}",
    )

async def _crg_ball_timeout(context):
    data = context.job.data
    state = await _crg_get(data["chat_id"])
    if not state or state.get("phase") != "live":
        return
    if state.get("ball_token") != data.get("token"):
        return
    bat = str(state["batting_uid"]); bowl = str(state["bowling_uid"])
    pending = state.setdefault("pending", {})
    if bat not in pending:
        pending[bat] = "defend"
    if bowl not in pending:
        pending[bowl] = "good"
    await _crg_resolve_ball(context, state)

async def cricket_match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("🏏 Start a Cricket Match inside a group so another member can play.")
        return
    chat_id = update.effective_chat.id
    u = update.effective_user
    existing = await _crg_get(chat_id)
    if existing and existing.get("phase") != "done":
        await update.message.reply_text("🏏 A cricket match is already running here. Finish it first.")
        return

    players = {str(u.id): {"uid": u.id, "name": u.first_name}}
    target_uid = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
        if target.id == u.id or target.is_bot:
            await update.message.reply_text("❌ Challenge a real member, not yourself or a bot.")
            return
        target_uid = target.id
        players[str(target.id)] = {"uid": target.id, "name": target.first_name}

    state = {
        "chat_id": chat_id, "phase": "waiting", "players": players,
        "target_uid": target_uid, "message_id": None,
        "scores": {str(u.id): {"runs": 0, "wickets": 0, "balls": 0, "fours": 0, "sixes": 0}},
        "created_at": datetime.now().isoformat(),
    }
    for p in players.values():
        state["scores"][str(p["uid"])] = {"runs": 0, "wickets": 0, "balls": 0, "fours": 0, "sixes": 0}

    if target_uid:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Accept Challenge", callback_data="crg:accept")]])
        text = (
            f"🏏 CRICKET CHALLENGE\n\n"
            f"{u.first_name} has challenged {players[str(target_uid)]['name']}.\n"
            f"Format: {CRG_MAX_OVERS} overs • {CRG_WICKETS} wickets\n\n"
            f"Only the challenged member can accept."
        )
    else:
        kb = _crg_kb_join()
        text = (
            f"🏏 CRICKET MATCH LOBBY\n\n"
            f"{u.first_name} is ready to play.\n"
            f"Format: {CRG_MAX_OVERS} overs per innings • {CRG_WICKETS} wickets\n\n"
            f"Another member: tap Join Match."
        )

    msg = await update.message.reply_text(text, reply_markup=kb)
    state["message_id"] = msg.message_id
    await _crg_save(chat_id, state)
    await _send_cricket_graphic(
        context, chat_id, "intro",
        caption="🏏 *CRICKET MATCH CENTRE*\n_The match is live. Make your move._",
    )
    context.job_queue.run_once(
        _crg_lobby_timeout, 300,
        data={"chat_id": chat_id, "created": state["created_at"]},
        name=f"crg_lobby_{chat_id}",
    )

async def _crg_lobby_timeout(context):
    data = context.job.data
    state = await _crg_get(data["chat_id"])
    if not state or state.get("phase") != "waiting":
        return
    if state.get("created_at") != data.get("created"):
        return
    state["phase"] = "done"
    state["result"] = "⏳ Match lobby expired. Start a new challenge when you're ready."
    await _crg_save(state["chat_id"], state)
    await _crg_edit(context, state, _crg_render(state), None)

async def cricket_match_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith("crgs:"):
        await _crgs_callback(update, context)
        return
    chat_id = q.message.chat.id
    state = await _crg_get(chat_id)
    if not state:
        await q.answer("⏳ This match has expired.", show_alert=True)
        return
    uid = q.from_user.id
    data = q.data

    if data == "crg:join":
        if state.get("phase") != "waiting":
            await q.answer("This lobby is closed.", show_alert=True); return
        if state.get("target_uid") is not None:
            await q.answer("This is a direct challenge.", show_alert=True); return
        p1 = next(iter(state["players"].values()))
        if uid == p1["uid"] or q.from_user.is_bot:
            await q.answer("You can't join your own match.", show_alert=True); return
        state["players"][str(uid)] = {"uid": uid, "name": q.from_user.first_name}
        for p in state["players"].values():
            state["scores"][str(p["uid"])] = {"runs": 0, "wickets": 0, "balls": 0, "fours": 0, "sixes": 0}
        state["phase"] = "toss"
        state["toss_uid"] = p1["uid"]
        await _crg_save(chat_id, state)
        await _crg_edit(
            context, state,
            f"{_crg_header(state)}\n\n🪙 Toss!\n{_crg_name(state, p1['uid'])} chooses Heads or Tails.",
            _crg_kb_toss(state)
        )
        await q.answer("You're in. Toss time.")
        return

    if data == "crg:accept":
        if state.get("phase") != "waiting" or state.get("target_uid") != uid:
            await q.answer("This challenge isn't yours.", show_alert=True); return
        state["phase"] = "toss"
        p1 = next(iter(state["players"].values()))
        state["toss_uid"] = p1["uid"]
        await _crg_save(chat_id, state)
        await _crg_edit(
            context, state,
            f"{_crg_header(state)}\n\n🪙 Toss!\n{_crg_name(state, p1['uid'])} chooses Heads or Tails.",
            _crg_kb_toss(state)
        )
        await q.answer("Challenge accepted. Toss time.")
        return

    if state.get("phase") == "toss" and data.startswith("crg:toss:"):
        if uid != state["toss_uid"]:
            await q.answer("The toss belongs to the other player.", show_alert=True); return
        call = data.split(":")[-1]
        result = random.choice(["H", "T"])
        winner = uid if call == result else next(p["uid"] for p in state["players"].values() if p["uid"] != uid)
        state["toss_winner"] = winner
        state["toss_call"] = call
        state["toss_result"] = result
        state["phase"] = "choose"
        await _crg_save(chat_id, state)
        await _crg_edit(
            context, state,
            f"{_crg_header(state)}\n\n🪙 Toss: {call} → {'Heads' if result == 'H' else 'Tails'}\n"
            f"🏆 { _crg_name(state, winner) } won the toss.\n\nChoose Bat First or Bowl First.",
            _crg_kb_bat_bowl()
        )
        return

    if state.get("phase") == "choose" and data in ("crg:batfirst", "crg:bowlfirst"):
        if uid != state["toss_winner"]:
            await q.answer("Only the toss winner chooses.", show_alert=True); return
        other = next(p["uid"] for p in state["players"].values() if p["uid"] != uid)
        if data == "crg:batfirst":
            bat, bowl = uid, other
        else:
            bat, bowl = other, uid
        state["first_batting_uid"] = bat
        state["second_batting_uid"] = bowl
        await _crg_start_innings(context, state, 1, bat, bowl, None)
        return

    if state.get("phase") != "live":
        return

    bat = state["batting_uid"]; bowl = state["bowling_uid"]
    if data.startswith("crg:shot:"):
        if uid != bat:
            await q.answer("You're bowling this ball.", show_alert=True); return
        action = data.split(":")[-1]
    elif data.startswith("crg:bowl:"):
        if uid != bowl:
            await q.answer("You're batting this ball.", show_alert=True); return
        action = data.split(":")[-1]
    else:
        return

    pending = state.setdefault("pending", {})
    if str(uid) in pending:
        await q.answer("You've already locked this ball.", show_alert=True); return
    pending[str(uid)] = action
    await _crg_save(chat_id, state)
    await q.answer("Locked in.")

    if str(bat) in pending and str(bowl) in pending:
        await _crg_resolve_ball(context, state)
    else:
        await _crg_edit(context, state, _crg_render(state) + f"\n\n⏳ {q.from_user.first_name} locked in.", _crg_kb_ball(state))


# ══════════════════════════════════════════════════════════════════════════
# CRICKET SOLO — single player vs Oracle AI
# Multiplayer above is unchanged. Solo uses its own Redis namespace/state.
# ══════════════════════════════════════════════════════════════════════════

CRGS_PREFIX = "crgs:"
CRGS_BOT_UID = -987654321

async def _crgs_get(uid):
    raw = await _rget(f"{CRGS_PREFIX}{uid}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        await _rdel(f"{CRGS_PREFIX}{uid}")
        return None

async def _crgs_save(uid, state):
    await _rsetex(f"{CRGS_PREFIX}{uid}", CRG_TTL, json.dumps(state, separators=(",", ":")))

async def _crgs_edit(context, state, text=None, keyboard=None):
    mid = state.get("message_id")
    if not mid:
        return
    if text is None:
        text = _crgs_render(state)
    try:
        await context.bot.edit_message_text(
            chat_id=state["chat_id"], message_id=mid, text=text, reply_markup=keyboard
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"[CricketSolo] edit failed: {e}")

def _crgs_name(state, uid):
    if uid == CRGS_BOT_UID:
        return "Oracle AI"
    return state["player_name"]

def _crgs_score(state, uid):
    return state["scores"].setdefault(str(uid), {"runs":0,"wickets":0,"balls":0,"fours":0,"sixes":0})

def _crgs_render(state):
    p = _crgs_score(state, state["player_uid"])
    ai = _crgs_score(state, CRGS_BOT_UID)
    text = (
        f"🏏 CRICKET SOLO — {state['player_name']} vs Oracle AI\n\n"
        f"👤 {state['player_name']}: {p['runs']}/{p['wickets']}\n"
        f"🤖 Oracle AI: {ai['runs']}/{ai['wickets']}\n"
    )
    if state["phase"] == "choose":
        text += "\nChoose your strategy for the match."
    elif state["phase"] == "live":
        over = state["legal_balls"] // 6
        ball = state["legal_balls"] % 6
        batter = _crgs_name(state, state["batting_uid"])
        bowler = _crgs_name(state, state["bowling_uid"])
        text += (
            f"\n📍 Innings {state['innings']} • Over {over}.{ball}\n"
            f"🏏 Batting: {batter}\n🎯 Bowling: {bowler}\n"
            f"🎯 Target: {state.get('target', '—')}\n"
        )
        if state["batting_uid"] == state["player_uid"]:
            text += "\n🏏 Choose your shot. Oracle is bowling."
        else:
            text += "\n🎯 Choose your delivery. Oracle is batting."
        if state.get("last_ball"):
            text += f"\n\n💬 {state['last_ball']}"
    elif state["phase"] == "done":
        text += f"\n\n🏆 {state.get('result', 'Match complete.')}"
    return text

def _crgs_kb_choice():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏏 Bat First", callback_data="crgs:batfirst"),
        InlineKeyboardButton("🎯 Bowl First", callback_data="crgs:bowlfirst"),
    ]])

def _crgs_kb_bat():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_CRG_SHOTS["defend"], callback_data="crgs:shot:defend"), InlineKeyboardButton(_CRG_SHOTS["drive"], callback_data="crgs:shot:drive")],
        [InlineKeyboardButton(_CRG_SHOTS["pull"], callback_data="crgs:shot:pull"), InlineKeyboardButton(_CRG_SHOTS["sweep"], callback_data="crgs:shot:sweep")],
        [InlineKeyboardButton(_CRG_SHOTS["loft"], callback_data="crgs:shot:loft"), InlineKeyboardButton(_CRG_SHOTS["slog"], callback_data="crgs:shot:slog")],
    ])

def _crgs_kb_bowl():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_CRG_BOWLS["yorker"], callback_data="crgs:bowl:yorker"), InlineKeyboardButton(_CRG_BOWLS["good"], callback_data="crgs:bowl:good")],
        [InlineKeyboardButton(_CRG_BOWLS["bouncer"], callback_data="crgs:bowl:bouncer"), InlineKeyboardButton(_CRG_BOWLS["slower"], callback_data="crgs:bowl:slower")],
        [InlineKeyboardButton(_CRG_BOWLS["spin"], callback_data="crgs:bowl:spin")],
    ])

async def _crgs_start_innings(context, state, innings, bat, bowl, target=None):
    state.update({"phase":"live", "innings":innings, "batting_uid":bat, "bowling_uid":bowl,
                  "legal_balls":0, "target":target, "last_ball":""})
    await _crgs_save(state["player_uid"], state)
    kb = _crgs_kb_bat() if bat == state["player_uid"] else _crgs_kb_bowl()
    await _crgs_edit(context, state, _crgs_render(state), kb)

def _crgs_ai_choice(state, batting):
    # Adaptive AI: mostly safe choices while chasing, more aggressive late in an innings.
    balls_left = CRG_MAX_OVERS * 6 - state["legal_balls"]
    if batting:
        choices = list(_CRG_SHOTS.keys())
        if balls_left <= 3 or (state.get("target") and state["target"] - _crgs_score(state, CRGS_BOT_UID)["runs"] <= 7):
            weights = [1, 1, 1, 1, 3, 4]
        else:
            weights = [3, 3, 1, 2, 1, 1]
    else:
        choices = list(_CRG_BOWLS.keys())
        weights = [3, 4, 2, 2, 3]
    return random.choices(choices, weights=weights, k=1)[0]

async def _crgs_finish(context, state, winner):
    puid = state["player_uid"]
    ps = _crgs_score(state, puid)
    ais = _crgs_score(state, CRGS_BOT_UID)
    state["phase"] = "done"
    if winner == puid:
        state["result"] = f"🏆 {state['player_name']} wins! Brilliant innings."
        await _addcoins(puid, 250)
    elif winner == CRGS_BOT_UID:
        state["result"] = "🤖 Oracle AI wins. The bot read your game."
        await _addcoins(puid, 75)
    else:
        state["result"] = "🤝 Match tied. Absolute thriller."
        await _addcoins(puid, 125)
    # Solo results use the same public cricket statistics, without recording the AI as a player.
    raw = await _rget(_crg_stats_key(puid))
    st = json.loads(raw) if raw else _crg_default_stats()
    st["matches"] += 1
    if winner == puid: st["wins"] += 1
    elif winner == CRGS_BOT_UID: st["losses"] += 1
    else: st["ties"] += 1
    st["runs"] += ps["runs"]; st["wickets"] += ps["wickets"]
    st["fours"] += ps["fours"]; st["sixes"] += ps["sixes"]
    await _rset(_crg_stats_key(puid), json.dumps(st))
    await _crgs_save(puid, state)
    await _send_cricket_graphic(context, state["chat_id"], "win", caption="🏆 *SOLO MATCH COMPLETE*\n_The scoreboard has been updated._")
    await _crgs_edit(context, state, _crgs_render(state), None)

async def _crgs_ball(context, state, player_action):
    bat = state["batting_uid"]
    player = state["player_uid"]
    if bat == player:
        shot, delivery = player_action, _crgs_ai_choice(state, False)
    else:
        shot, delivery = _crgs_ai_choice(state, True), player_action
    result = _crg_ball_result(shot, delivery)
    s = _crgs_score(state, bat)
    s["balls"] += 1
    if result["wicket"]:
        s["wickets"] += 1
    else:
        s["runs"] += result["runs"]
        if result["runs"] == 4: s["fours"] += 1
        if result["runs"] == 6: s["sixes"] += 1
    state["scores"][str(bat)] = s
    state["legal_balls"] += 1
    state["last_ball"] = f"{result['text']} ({shot.title()} vs {delivery.title()})"

    graphic_kind = "wicket" if result["wicket"] else ("six" if result["runs"] == 6 else ("four" if result["runs"] == 4 else None))
    if graphic_kind:
        await _send_cricket_graphic(context, state["chat_id"], graphic_kind)

    target = state.get("target")
    if target and s["runs"] >= target:
        await _crgs_finish(context, state, bat)
        return
    if s["wickets"] >= CRG_WICKETS or state["legal_balls"] >= CRG_MAX_OVERS * 6:
        if state["innings"] == 1:
            other = CRGS_BOT_UID if bat == player else player
            await _crgs_start_innings(context, state, 2, other, bat, s["runs"] + 1)
            return
        ps = _crgs_score(state, player)["runs"]
        ais = _crgs_score(state, CRGS_BOT_UID)["runs"]
        if ps == ais:
            # Keep solo matches decisive without introducing an extra UI state.
            state["innings"] = 1
            state["super_over"] = True
            state["scores"][str(player)]["runs"] = 0
            state["scores"][str(CRGS_BOT_UID)]["runs"] = 0
            await _crgs_start_innings(context, state, 3, player, CRGS_BOT_UID, None)
            return
        await _crgs_finish(context, state, player if ps > ais else CRGS_BOT_UID)
        return
    await _crgs_save(player, state)
    kb = _crgs_kb_bat() if state["batting_uid"] == player else _crgs_kb_bowl()
    await _crgs_edit(context, state, _crgs_render(state), kb)

async def cricket_solo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup", "private"):
        return
    uid = update.effective_user.id
    existing = await _crgs_get(uid)
    if existing and existing.get("phase") != "done":
        await update.message.reply_text("🏏 You already have a solo match running. Finish it first.")
        return
    state = {
        "chat_id": update.effective_chat.id, "player_uid": uid,
        "player_name": update.effective_user.first_name or "Player",
        "phase": "choose", "message_id": None,
        "scores": {str(uid): {"runs":0,"wickets":0,"balls":0,"fours":0,"sixes":0},
                    str(CRGS_BOT_UID): {"runs":0,"wickets":0,"balls":0,"fours":0,"sixes":0}},
    }
    msg = await update.message.reply_text(
        "🏏 CRICKET SOLO\n\n"
        f"{state['player_name']} 🆚 Oracle AI 🤖\n\n"
        f"{CRG_MAX_OVERS} overs per innings • {CRG_WICKETS} wickets\n"
        "You control your side. The AI plays the other side.\n\n"
        "Choose your innings:",
        reply_markup=_crgs_kb_choice(),
    )
    state["message_id"] = msg.message_id
    await _crgs_save(uid, state)
    await _send_cricket_graphic(
        context, update.effective_chat.id, "intro",
        caption="🏏 *SOLO CRICKET CENTRE*\n_Oracle AI is ready._",
    )

async def _crgs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    state = await _crgs_get(uid)
    if not state:
        await q.answer("Your solo match has expired.", show_alert=True); return
    data = q.data
    if data in ("crgs:batfirst", "crgs:bowlfirst"):
        if state.get("phase") != "choose":
            await q.answer("Match already started.", show_alert=True); return
        if data == "crgs:batfirst":
            bat, bowl = uid, CRGS_BOT_UID
        else:
            bat, bowl = CRGS_BOT_UID, uid
        state["first_batting_uid"] = bat
        await _crgs_start_innings(context, state, 1, bat, bowl, None)
        await q.answer("Match on! 🏏")
        return
    if state.get("phase") != "live":
        await q.answer("This match is over.", show_alert=True); return
    if state["batting_uid"] == uid and data.startswith("crgs:shot:"):
        action = data.split(":")[-1]
    elif state["bowling_uid"] == uid and data.startswith("crgs:bowl:"):
        action = data.split(":")[-1]
    else:
        await q.answer("That's the AI's side.", show_alert=True); return
    await _crgs_ball(context, state, action)
    await q.answer("Played! 🏏")

async def cricket_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else u
    raw = await _rget(_crg_stats_key(target.id))
    st = json.loads(raw) if raw else _crg_default_stats()
    wr = round(st["wins"] / st["matches"] * 100, 1) if st["matches"] else 0
    await update.message.reply_text(
        f"🏏 CRICKET CARD — {target.first_name}\n\n"
        f"Matches: {st['matches']}\nWins: {st['wins']} • Losses: {st['losses']} • Ties: {st['ties']}\n"
        f"Win rate: {wr}%\n\n"
        f"Runs: {st['runs']} • Wickets: {st['wickets']}\n"
        f"Fours: {st['fours']} • Sixes: {st['sixes']}"
    )

async def cricket_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = await _rkeys("cricket_stats:*")
    board = []
    for key in keys or []:
        try:
            uid = int(key.split(":")[-1])
            raw = await _rget(key)
            st = json.loads(raw) if raw else _crg_default_stats()
            board.append((st.get("wins", 0), st.get("runs", 0), uid, st))
        except Exception:
            continue
    board.sort(reverse=True, key=lambda x: (x[0], x[1]))
    if not board:
        await update.message.reply_text("🏏 No cricket records yet. Start a match with /cricketmatch.")
        return
    lines = []
    for i, (wins, runs, uid, st) in enumerate(board[:10], 1):
        try:
            member = await context.bot.get_chat(uid)
            name = member.first_name or "Player"
        except Exception:
            name = "Player"
        lines.append(f"{i}. {name} — {wins}W • {runs} runs")
    await update.message.reply_text("🏆 CRICKET LEADERBOARD\n\n" + "\n".join(lines))

async def cricket_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏏 CRICKET MATCH\n\n"
        "/cricketmatch — open a 1v1 lobby\n"
        "Reply to a member with /cricketmatch to challenge them directly.\n\n"
        "Toss → Bat/Bowl → choose your shot/delivery every ball.\n"
        f"{CRG_MAX_OVERS} overs per innings • {CRG_WICKETS} wickets • live scorecard.\n"
        "If the match is tied, the bot runs a Super Over.\n\n"
        "/cricketstats — your cricket record\n"
        "/cricketleaderboard — top players"
    )


# ══════════════════════════════════════════════════════════════════════════
# DEATH GAMES — survival, elimination, drama
# ══════════════════════════════════════════════════════════════════════════

_DEATH_SCENARIOS = [
    "The Oracle locks the group in a haunted mansion. Only one survives.",
    "A storm traps everyone. Resources run out. Alliances break.",
    "The Oracle runs an underground tournament. No rules. No mercy.",
    "Someone in the group is the Oracle's chosen one. Others must find them.",
    "The void opens. One by one, people get pulled in.",
]

_SURVIVAL_ACTIONS = [
    "hid in the shadows and survived another round 🌑",
    "formed a secret alliance 🤝",
    "outsmarted the Oracle's trap 👁️",
    "sacrificed their coins to survive 💀",
    "found a hidden immunity 🔱",
    "was saved by another player 🫂",
    "went ghost mode and nobody could find them 👻",
]

_ELIMINATION_MSGS = [
    "💀 *ELIMINATED*\n\n*{name}* didn't make it.\n_The Oracle thanks them for playing._ 🖤",
    "🌑 *{name}* has fallen.\n\n_Even the stars couldn't save them._ 👁️",
    "💀 *THE VOID CLAIMED {name}*\n\n_Better luck in the next life._ 🌙",
    "🔱 *{name}* is out.\n\n_The Oracle watched. Did nothing. That's the game._ 👀",
]

async def deathgame_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user

    if await _rexists(f"dg_active:{chat_id}"):
        await update.message.reply_text("💀 A death game is already running. /dgjoin to enter.")
        return

    scenario = random.choice(_DEATH_SCENARIOS)
    await _rsetex(f"dg_active:{chat_id}", 86400, "collecting")
    await _rdel(f"dg_players:{chat_id}")

    await update.message.reply_text(
        f"💀 *THE ORACLE OPENS THE DEATH GAME*\n\n"
        f"_{scenario}_\n\n"
        f"Type `/dgjoin` to enter. You have *5 minutes.*\n"
        f"Minimum 3 players needed.\n\n"
        f"_Not everyone makes it out._ 🌑",
        parse_mode=ParseMode.MARKDOWN
    )

    context.job_queue.run_once(
        _start_death_rounds,
        300,
        data={"chat_id": chat_id},
        name=f"dg_{chat_id}"
    )

async def dgjoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = update.effective_user

    if not await _rexists(f"dg_active:{chat_id}"):
        await update.message.reply_text("🌑 No death game running. Start one with /deathgame")
        return

    status = await _rget(f"dg_active:{chat_id}")
    if status != "collecting":
        await update.message.reply_text("💀 Game already started. Watch and suffer.")
        return

    raw = await _rget(f"dg_players:{chat_id}")
    players = json.loads(raw) if raw else []

    if any(p["uid"] == u.id for p in players):
        await update.message.reply_text(f"👁️ {u.first_name}, you're already in. Wait for it to start.")
        return

    players.append({"uid": u.id, "name": u.first_name, "alive": True, "coins_staked": 100})
    await _rset(f"dg_players:{chat_id}", json.dumps(players))
    await _addcoins(u.id, -min(100, await _coins(u.id)))

    try: await update.message.delete()
    except: pass

    joins = [
        f"👁️ *{u.first_name}* entered the game. bold. 🌑",
        f"💀 *{u.first_name}* joined. the Oracle notes their bravery.",
        f"🔱 *{u.first_name}* is in. {len(players)} players so far.",
        f"🌙 *{u.first_name}* steps into the void. no turning back.",
    ]
    await context.bot.send_message(chat_id, random.choice(joins), parse_mode=ParseMode.MARKDOWN)

async def _start_death_rounds(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]

    raw = await _rget(f"dg_players:{chat_id}")
    players = json.loads(raw) if raw else []

    if len(players) < 3:
        await _rdel(f"dg_active:{chat_id}", f"dg_players:{chat_id}")
        # Refund
        for p in players:
            await _addcoins(p["uid"], 100)
        await context.bot.send_message(
            chat_id,
            "🌑 Not enough players. Death game cancelled.\n_Coins refunded._ 💰",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await _rset(f"dg_active:{chat_id}", "running")
    prize_pool = len(players) * 100

    await context.bot.send_message(
        chat_id,
        f"💀 *THE GAME BEGINS*\n\n"
        f"Players: `{len(players)}`\n"
        f"Prize pool: `{prize_pool}` coins 🏆\n\n"
        f"_The Oracle will eliminate one player per round._ 👁️",
        parse_mode=ParseMode.MARKDOWN
    )

    await asyncio.sleep(3)

    # Run elimination rounds
    alive = [p for p in players]
    round_num = 1

    while len(alive) > 1:
        await asyncio.sleep(random.uniform(8, 15))  # dramatic pause

        # Survival messages for survivors
        survivors = random.sample(alive, min(len(alive)-1, len(alive)))
        survival_lines = []
        for p in survivors[:3]:  # show max 3 survival actions
            action = random.choice(_SURVIVAL_ACTIONS)
            survival_lines.append(f"✅ *{p['name']}* {action}")

        # Eliminate one
        victim = random.choice(alive)
        alive = [p for p in alive if p["uid"] != victim["uid"]]

        elim_msg = random.choice(_ELIMINATION_MSGS).replace("{name}", victim["name"])

        round_text = f"🌑 *ROUND {round_num}*\n\n"
        if survival_lines:
            round_text += "\n".join(survival_lines) + "\n\n"
        round_text += elim_msg

        await context.bot.send_message(chat_id, round_text, parse_mode=ParseMode.MARKDOWN)
        round_num += 1

    # Winner
    if alive:
        winner = alive[0]
        await _addcoins(winner["uid"], prize_pool)
        await context.bot.send_message(
            chat_id,
            f"🏆 *THE LAST ONE STANDING*\n\n"
            f"*{winner['name']}* survived everything.\n\n"
            f"🪙 Prize: `{prize_pool}` coins\n\n"
            f"_The Oracle bows. Just once. 🌙_",
            parse_mode=ParseMode.MARKDOWN
        )

    await _rdel(f"dg_active:{chat_id}", f"dg_players:{chat_id}")

async def dgstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    status = await _rget(f"dg_active:{chat_id}")
    if not status:
        await update.message.reply_text("🌑 No death game active.\n_/deathgame to start one._ 🌙", parse_mode=ParseMode.MARKDOWN)
        return
    raw = await _rget(f"dg_players:{chat_id}")
    players = json.loads(raw) if raw else []
    names = ", ".join(p["name"] for p in players) or "none yet"
    await update.message.reply_text(
        f"💀 *DEATH GAME STATUS*\n\nPlayers: `{len(players)}`\n_{names}_\n\nStatus: `{status}`",
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
    # ── read me ──
    BotCommand("start",         "🌙 wake the oracle"),
    BotCommand("help",          "👁️ what can i do"),

    # ── who are you ──
    BotCommand("oracle",        "🔮 what the oracle sees in you today"),
    BotCommand("aura",          "🌈 your aura, read"),
    BotCommand("vibecheck",     "✨ full vibe scan"),
    BotCommand("identity",      "🃏 your oracle identity"),
    BotCommand("shadow",        "🌑 your shadow self, named"),
    BotCommand("element",       "🌌 your cosmic element"),
    BotCommand("corecode",      "🔱 three words. that's you."),
    BotCommand("duality",       "☯️ your light. your dark."),
    BotCommand("nightreport",   "🌙 tonight's energy reading"),
    BotCommand("sigil",         "✦ your sigil, drawn"),
    BotCommand("universe",      "💫 what the universe wants you to hear"),
    BotCommand("ritual",        "🕯️ one thing to do before midnight"),
    BotCommand("glitch",        "⚡ when the oracle breaks"),

    # ── the economy of shadows ──
    BotCommand("checkin",       "🌙 show up. earn something."),
    BotCommand("balance",       "💰 what you've accumulated"),
    BotCommand("daily",         "🪙 your daily offering"),
    BotCommand("coinboard",     "🏆 who holds the most"),
    BotCommand("cgift",         "💝 give some away — reply to use"),
    BotCommand("rob",           "🦹 take what isn't yours — reply"),
    BotCommand("wallet",        "🏦 your vault. untouchable."),
    BotCommand("deposit",       "🔒 hide it"),
    BotCommand("withdraw",      "🔓 take it back"),

    # ── games of chance ──
    BotCommand("bet",           "🎲 50/50. you decide."),
    BotCommand("mines",         "💣 one wrong move."),
    BotCommand("duel",          "⚔️ settle it — reply to challenge"),
    BotCommand("mysterybox",    "🎁 spend 100. see what the void gives back."),
    BotCommand("fastmath",      "⚡ first correct answer wins"),
    BotCommand("wordbomb",      "💣 chain or lose"),
    BotCommand("rps",           "✊ classic. still works."),
    BotCommand("dice",          "🎲 roll it"),
    BotCommand("roulette",      "💀 one chamber. your call."),
    BotCommand("8ball",         "🎱 ask. receive."),

    # ── group chaos ──
    BotCommand("verdict",       "👁️ oracle calls someone out"),
    BotCommand("hotseat",       "🔥 put someone on the spot"),
    BotCommand("silence",       "🌑 no one talks. or else."),
    BotCommand("truth",         "😬 answer it"),
    BotCommand("dare",          "😤 do it"),
    BotCommand("wyr",           "🤔 pick one"),

    # ── cricket ──
    BotCommand("cricket",       "🏏 oracle reacts to the match"),
    BotCommand("cpredict",      "🔮 start a match prediction"),
    BotCommand("cbet",          "🏏 bet on a team"),
    BotCommand("cwin",          "🏆 declare winner — admin"),
    BotCommand("ctournament",   "🏏 start mini tournament"),
    BotCommand("cpick",         "✅ pick your team"),
    BotCommand("cplay",         "⚡ simulate a match — admin"),
    BotCommand("broadcast",     "📡 send to all groups — owner dm"),

    # ── death games ──
    BotCommand("deathgame",     "💀 start the elimination game"),
    BotCommand("dgjoin",        "🌑 enter the game"),
    BotCommand("dgstatus",      "👁️ who's still alive"),

    # ── feelings ──
    BotCommand("hug",           "🤗 reach out — reply to use"),
    BotCommand("pat",           "🥺 quiet comfort — reply to use"),
    BotCommand("slap",          "👋 deserved — reply to use"),
    BotCommand("kiss",          "💋 bold move — reply to use"),
    BotCommand("poke",          "👉 hey. hey. — reply to use"),
    BotCommand("cuddle",        "🫂 stay close — reply to use"),
    BotCommand("bite",          "😈 claimed — reply to use"),
    BotCommand("wave",          "👋 i see you — reply to use"),
    BotCommand("highfive",      "🙌 let's go — reply to use"),
    BotCommand("compliment",    "💐 say something good"),
    BotCommand("roast",         "🔥 say something chaotic"),
    BotCommand("ship",          "💞 two people. one fate."),
    BotCommand("rank",          "👑 oracle decides your title"),

    # ── secrets ──
    BotCommand("vent",          "🫀 say it without your name"),
    BotCommand("confess",       "🤫 confess. oracle carries it."),
    BotCommand("startcouple",   "💞 secret pairing. 24 hours."),
    BotCommand("joincouple",    "🌙 enter the pool"),
    BotCommand("mymission",     "🕯️ your secret task — dm only"),
    BotCommand("crush",         "💘 you know who"),
    BotCommand("secretadmirer", "💌 anonymous. always."),

    # ── bonds ──
    BotCommand("marry",         "💍 make it official — reply to use"),
    BotCommand("divorce",       "💔 end it"),
    BotCommand("profile",       "👤 your oracle record"),
    BotCommand("friendship",    "💫 how compatible are you two"),
    BotCommand("bestie",        "👯 declare it"),
    BotCommand("duo",           "🤝 your duo name, generated"),

    # ── admin shadows ──
    BotCommand("ban",           "🔨 gone — admin"),
    BotCommand("mute",          "🔇 silenced — admin"),
    BotCommand("warn",          "⚠️ noted — admin"),
    BotCommand("purge",         "🗑️ erased — admin"),
    BotCommand("oraclehour",    "⚡ open the event — admin"),
    BotCommand("enter",         "🎯 claim your spot"),
    BotCommand("poll",          "📊 let them vote"),
    BotCommand("afk",           "💤 i'm gone for now"),
]

# ══════════════════════════════════════════════════════════════════════════
# STARTUP + MAIN
# ══════════════════════════════════════════════════════════════════════════
async def _post_init(app: Application):
    # Register the complete Midnight command list in DMs
    await app.bot.set_my_commands(
        BOT_COMMANDS,
        scope=BotCommandScopeAllPrivateChats(),
    )

    # Register the SAME complete command list in every group
    await app.bot.set_my_commands(
        BOT_COMMANDS,
        scope=BotCommandScopeAllGroupChats(),
    )

    logger.info(
        "✅ Commands registered everywhere (%d)",
        len(BOT_COMMANDS),
    )

    await economy.load_from_storage()
    logger.info("✅ Economy loaded")
    await economy.load_from_storage(); logger.info("✅ Economy loaded")
    await timecapsule.load_and_reschedule(app); logger.info("✅ Capsules rescheduled")
    await chat.load_from_storage(); logger.info("✅ Chat settings loaded")
    await marriage.load_from_storage(); logger.info("✅ Marriage data loaded")
    await deathgames.load_from_storage(); logger.info("✅ Death Games loaded")
    await _load_known_groups(); logger.info("✅ Known groups loaded")

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

    # Oracle Verdicts
    app.add_handler(CommandHandler("verdict", verdict_command))
    app.add_handler(CommandHandler("hotseat", hotseat_command))

    # Silence Game
    app.add_handler(CommandHandler("silence", silence_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, silence_watcher), group=12)

    # Cricket — full system
    app.add_handler(CommandHandler("cricket", cricket_command))
    app.add_handler(CommandHandler("cpredict", cricket_predict_command))
    app.add_handler(CommandHandler("cbet", cricket_bet_command))
    app.add_handler(CommandHandler("cwin", cricket_win_command))
    app.add_handler(CommandHandler("ctournament", cricket_tournament_command))
    app.add_handler(CommandHandler("cpick", cricket_pick_command))
    app.add_handler(CommandHandler("cplay", cricket_play_command))
    app.add_handler(CommandHandler("cricketmatch", cricket_match_command))
    app.add_handler(CommandHandler("cricketsolo", cricket_solo_command))
    app.add_handler(CommandHandler("cricketstats", cricket_stats_command))
    app.add_handler(CommandHandler("cricketleaderboard", cricket_leaderboard_command))
    app.add_handler(CommandHandler("crickethelp", cricket_help_command))
    app.add_handler(CallbackQueryHandler(cricket_match_callback, pattern=r"^crg:"))
    app.add_handler(CallbackQueryHandler(_crgs_callback, pattern=r"^crgs:"))

    # Broadcast — owner only via DM
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("announce", announce_command))

    # Group tracker — knows which groups bot is in
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, track_groups), group=15)
    app.add_handler(MessageHandler(filters.ALL, track_group_migration), group=16)

    # Death Games (new Oracle version)
    app.add_handler(CommandHandler("deathgame", deathgame_start))
    app.add_handler(CommandHandler("dgjoin", dgjoin_command))
    app.add_handler(CommandHandler("dgstatus", dgstatus_command))

    # Member + message trackers
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, track_members), group=13)
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, track_msg_count), group=14)

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

    # Oracle verdict — every 6 hours picks someone and calls them out
    app.job_queue.run_repeating(oracle_verdict, interval=21600, first=3600, name="verdict_job")

    # Night mode — checks every hour if it's late night
    app.job_queue.run_repeating(night_mode_check, interval=3600, first=300, name="night_mode")

    # Weekly titles — every Sunday at 8pm
    app.job_queue.run_daily(
        weekly_titles,
        datetime.strptime("20:00", "%H:%M").time(),
        days=(6,),
        name="weekly_titles"
    )
    logger.info("✅ Verdict, night mode, weekly titles jobs registered")

    # Webhook
    full_url=f"{RENDER_EXTERNAL_URL}/{TOKEN}"
    logger.info("🌙 Midnight Oracle awakening... webhook at %s",full_url)
    app.run_webhook(listen="0.0.0.0",port=PORT,url_path=TOKEN,webhook_url=full_url)

if __name__=="__main__":
    main()
