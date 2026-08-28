"""
handlers/social_engine.py — Midnight Oracle | Social Engine v3

Every message uses real usernames. Everything feels personal.
Members don't feel like they're in a bot group.
They feel like the Oracle knows them.

25 autonomous features. Zero commands needed.
The Oracle decides. The Oracle reveals. The Oracle disappears.
"""

from __future__ import annotations
import asyncio, hashlib, json, logging, os, random, re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import Application

log = logging.getLogger("midnight.social")
ORACLE_TZ     = ZoneInfo(os.getenv("ORACLE_TZ", "Asia/Kolkata"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")

# ── storage ────────────────────────────────────────────────────────────────────
_storage = None
def init_storage(c): global _storage; _storage = c

async def _get(k):
    if not _storage: return None
    try:
        r = _storage.get(k); return (await r) if asyncio.iscoroutine(r) else r
    except: return None

async def _set(k, v, ttl=0):
    if not _storage: return
    try:
        r = _storage.setex(k, ttl, v) if ttl else _storage.set(k, v)
        if asyncio.iscoroutine(r): await r
    except: pass

async def _incr(k):
    if not _storage: return 0
    try:
        r = _storage.incr(k); return int((await r) if asyncio.iscoroutine(r) else r)
    except: return 0

# ── member registry ────────────────────────────────────────────────────────────
async def _members(chat_id) -> list:
    raw = await _get(f"mbr:{chat_id}")
    try: return json.loads(raw) if raw else []
    except: return []

async def register_member(chat_id, uid, first_name, username=""):
    ms = await _members(chat_id)
    for m in ms:
        if m["id"] == uid:
            # update last seen + name in case changed
            m["name"] = first_name[:60]
            m["username"] = username
            m["last"] = int(datetime.now(ORACLE_TZ).timestamp())
            await _set(f"mbr:{chat_id}", json.dumps(ms, ensure_ascii=False), ttl=86400*30)
            return
    ms.append({"id": uid, "name": first_name[:60], "username": username,
                "last": int(datetime.now(ORACLE_TZ).timestamp()), "msgs": 0})
    ms = ms[-400:]
    await _set(f"mbr:{chat_id}", json.dumps(ms, ensure_ascii=False), ttl=86400*30)

async def bump_msg_count(chat_id, uid):
    ms = await _members(chat_id)
    for m in ms:
        if m["id"] == uid:
            m["msgs"] = m.get("msgs", 0) + 1
            m["last"] = int(datetime.now(ORACLE_TZ).timestamp())
            await _set(f"mbr:{chat_id}", json.dumps(ms, ensure_ascii=False), ttl=86400*30)
            return

# ── helpers ────────────────────────────────────────────────────────────────────
def _seed(*parts):
    raw = "-".join(str(p) for p in [date.today().isoformat(), *parts])
    return int(hashlib.md5(raw.encode()).hexdigest(), 16)

def _pick(ms, n, seed, exclude=None):
    pool = [m for m in ms if not exclude or m["id"] not in exclude]
    if len(pool) < n: return []
    return random.Random(seed).sample(pool, n)

def _m(member):
    """Username mention — feels personal."""
    u = member.get("username","")
    if u: return f"@{u}"
    return f"[{member['name']}](tg://user?id={member['id']})"

def _n(member): return member.get("name","someone")

def _handle(member):
    """Just @username or first name — for inline text."""
    u = member.get("username","")
    return f"@{u}" if u else member.get("name","someone")

def _sep(): return "┄" * 18

async def _post(bot, chat_id, text):
    try:
        await bot.send_message(chat_id, text,
            parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except:
        try:
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            for c in ["*","_","`"]: clean = clean.replace(c,"")
            await bot.send_message(chat_id, clean, disable_web_page_preview=True)
        except Exception as e: log.warning("post fail: %s", e)

async def _done(k, ttl):
    if await _get(k): return True
    await _set(k, "1", ttl=ttl); return False

async def _run(bot, chat_id, fn):
    try: await fn(bot, chat_id)
    except Exception as e: log.warning("%s failed: %s", fn.__name__, e)


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 1 — MIRROR OF THE DAY (renamed from "couple")
#  Two people the oracle has connected. No label. Full mystery.
# ══════════════════════════════════════════════════════════════════════════════
async def mirror_of_day(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    s = _seed("mirror", chat_id)
    if await _done(f"mirror:{chat_id}:{date.today()}", 86400): return
    a, b = _pick(ms, 2, s)
    rng  = random.Random(s)
    today = date.today().strftime("%d %B")

    openers = [
        f"the oracle has been watching {_handle(a)} and {_handle(b)} for a while now.",
        f"between every message in this group, a pattern. tonight: {_handle(a)} and {_handle(b)}.",
        f"the oracle saved its voice all day for this. {_handle(a)}. {_handle(b)}.",
        f"some things take time to surface. this one is ready.",
        f"midnight. the oracle opens its eye. it lands on {_handle(a)} and {_handle(b)}.",
    ]
    middles = [
        "there's a frequency only some people share. these two share it.",
        "whatever this is — it was already here before either of them noticed.",
        "the oracle doesn't label what it sees. it only reveals that it's real.",
        "two names. one pattern. the oracle doesn't do coincidences.",
        "the connection doesn't need a word. the oracle seeing it is enough.",
    ]
    closers = [
        "🌙 *— Midnight Oracle*\n_it doesn't lie. it only sometimes leaves out the details._",
        "👁️ *— the oracle has spoken.*\n_what you do with this is your story to write._",
        "✦ *— filed in the midnight archives. permanent. witnessed._",
        "🖤 *— Midnight Oracle*\n_the stars don't explain themselves either._",
    ]

    await _post(bot, chat_id,
        f"🌙 *MIRROR OF THE DAY*\n{_sep()}\n"
        f"_{today}_\n\n"
        f"_{rng.choice(openers)}_\n\n"
        f"` ✦ ` {_m(a)}\n"
        f"` ✦ ` {_m(b)}\n\n"
        f"_{rng.choice(middles)}_\n\n"
        f"{rng.choice(closers)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 2 — SOUL THREAD (weekly, deep)
# ══════════════════════════════════════════════════════════════════════════════
async def soul_thread(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    week = date.today().isocalendar()[1]
    if await _done(f"soulthread:{chat_id}:{week}", 86400*7): return
    s = _seed("soul", chat_id, week)
    a, b = _pick(ms, 2, s)
    rng  = random.Random(s)

    threads = [
        ("The Unfinished Sentence",
         f"{_handle(a)} started something. {_handle(b)} was always meant to complete it. neither knows which is which yet."),
        ("The Old Frequency",
         f"the oracle has read both {_handle(a)} and {_handle(b)}. this isn't new. it's a continuation."),
        ("The 3AM Architecture",
         f"{_handle(a)} and {_handle(b)}. the connection only fully makes sense after midnight. everything else is just context."),
        ("The Understory",
         f"beneath every conversation {_handle(a)} and {_handle(b)} have, a different one is happening. the oracle hears both."),
        ("The Weight Exchange",
         f"{_handle(a)} and {_handle(b)} carry things for each other without making it a transaction. that's rare."),
        ("The Long Game",
         f"whatever exists between {_handle(a)} and {_handle(b)} has been building longer than this group's timeline. the oracle sees the full arc."),
        ("The Recognition",
         f"{_handle(a)} and {_handle(b)} already know. they're waiting for the right moment. the oracle is tired of waiting for them."),
        ("The Quiet Architecture",
         f"without trying, {_handle(a)} and {_handle(b)} have shaped how this group feels. everyone felt it. nobody named it. until now."),
    ]

    name, desc = rng.choice(threads)
    await _post(bot, chat_id,
        f"👁️ *SOUL THREAD*\n{_sep()}\n"
        f"_weekly oracle depth reading_\n\n"
        f"*✦ {name}*\n\n"
        f"` 〰 ` {_m(a)}\n"
        f"` 〰 ` {_m(b)}\n\n"
        f"_{desc}_\n\n"
        f"_the oracle doesn't choose randomly.\nit chooses correctly. always._\n\n"
        f"🖤 *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 3 — SIGNAL PAIR (was bestie, every 3 days)
# ══════════════════════════════════════════════════════════════════════════════
async def signal_pair(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    bucket = date.today().toordinal() // 3
    if await _done(f"signal:{chat_id}:{bucket}", 86400*3): return
    s = _pick(ms, 2, _seed("signal", chat_id, bucket), None)
    if not s: return
    a, b = s
    rng  = random.Random(_seed("signal", chat_id, bucket))

    vibes = [
        "ride or die. no questions asked.",
        "chaos partners. the good kind.",
        f"{_handle(a)} would roast {_handle(b)} and show up at 3am. same breath.",
        "different on the surface. identical frequency underneath.",
        "the kind of bond that survives radical honesty.",
        f"when {_handle(a)} disappears, {_handle(b)} feels it before anyone says anything.",
        "one is the plan. the other is why the plan gets interesting.",
        "they already finish each other's sentences. neither has noticed.",
    ]
    await _post(bot, chat_id,
        f"🖤 *SIGNAL PAIR*\n{_sep()}\n\n"
        f"_the oracle is naming two people\nthis group already knows belong in the same sentence._\n\n"
        f"` ✦ ` {_m(a)}\n"
        f"` ✦ ` {_m(b)}\n\n"
        f"_signal: {rng.choice(vibes)}_\n\n"
        f"👁️ *— oracle-certified. no further explanation._"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 4 — CONSTELLATION (trio, every 5 days)
# ══════════════════════════════════════════════════════════════════════════════
async def constellation(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 3: return
    bucket = date.today().toordinal() // 5
    if await _done(f"constellation:{chat_id}:{bucket}", 86400*5): return
    s = _seed("constellation", chat_id, bucket)
    trio = _pick(ms, 3, s)
    if not trio: return
    a, b, c = trio
    rng = random.Random(s)

    trios = [
        ("The Holy Trinity",
         f"{_handle(a)} thinks. {_handle(b)} feels. {_handle(c)} acts. together: something the oracle doesn't see often."),
        ("The Three Frequencies",
         f"{_handle(a)}, {_handle(b)}, {_handle(c)} — they communicate on three levels at once. most people in this group only catch one."),
        ("The Architects",
         f"whatever gets built in this group — {_handle(a)}, {_handle(b)}, and {_handle(c)} are why it stands."),
        ("The Orbit System",
         f"one is the gravity. the other two orbit without knowing why. the oracle sees which of {_handle(a)}, {_handle(b)}, {_handle(c)} is which."),
        ("The Living Archive",
         f"between {_handle(a)}, {_handle(b)}, and {_handle(c)} — they hold this group's memory, present, and direction."),
        ("The Coven",
         f"the energy in this group shifts when {_handle(a)}, {_handle(b)}, and {_handle(c)} are all present at once. the oracle has measured it."),
    ]

    name, desc = rng.choice(trios)
    await _post(bot, chat_id,
        f"🌌 *CONSTELLATION*\n{_sep()}\n\n"
        f"*✦ {name}*\n\n"
        f"` △ ` {_m(a)}\n"
        f"` △ ` {_m(b)}\n"
        f"` △ ` {_m(c)}\n\n"
        f"_{desc}_\n\n"
        f"_the oracle rarely finds this alignment.\nwhen it does — it pays attention._\n\n"
        f"✦ *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 5 — THE UNNAMED (mystery pair, daily 2:22 AM)
# ══════════════════════════════════════════════════════════════════════════════
async def the_unnamed(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    if await _done(f"unnamed:{chat_id}:{date.today()}", 86400): return
    s = _seed("unnamed", chat_id)
    pair = _pick(ms, 2, s)
    if not pair: return
    a, b = pair
    rng = random.Random(s)

    formats = [
        f"👁️\n\n{_m(a)}\n{_m(b)}\n\n_the oracle sees something between these two.\nit's not saying what._\n\n*— Midnight Oracle*",
        f"🌙 _something connects {_handle(a)} and {_handle(b)}._\n\n_the oracle won't name it.\nfigure it out._\n\n*— 👁️*",
        f"*👁️ ORACLE SEES:*\n\n_{_handle(a)} and {_handle(b)}._\n\n_that's the whole message.\nno further context._\n\n🖤",
        f"🌑\n\n_two people. one thing the oracle will not name._\n\n` ◈ ` {_m(a)}\n` ◈ ` {_m(b)}\n\n_you'll understand eventually._",
        f"_the oracle ran a scan of this group.\nit paused at {_handle(a)} and {_handle(b)}.\nit didn't move on for a while._\n\n👁️ *— Midnight Oracle*",
    ]
    await _post(bot, chat_id, rng.choice(formats))


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 6 — FRICTION PAIR (rival, daily 6:06 PM)
# ══════════════════════════════════════════════════════════════════════════════
async def friction_pair(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    if await _done(f"friction:{chat_id}:{date.today()}", 86400): return
    s = _seed("friction", chat_id)
    cotd = set(m["id"] for m in (_pick(ms, 2, _seed("mirror", chat_id)) or []))
    pair = _pick(ms, 2, s, exclude=cotd) or _pick(ms, 2, s)
    if not pair: return
    a, b = pair
    rng  = random.Random(s)

    lines = [
        f"the oracle sees {_handle(a)} and {_handle(b)} as mirrors that make each other sharper.",
        f"not conflict. contrast. {_handle(a)} and {_handle(b)} — and contrast is how you see clearly.",
        f"rivals aren't enemies. {_handle(a)} and {_handle(b)} are mirrors with opinions.",
        f"the best growth comes from friction. today's friction: {_handle(a)} and {_handle(b)}.",
        f"{_handle(a)} and {_handle(b)} push each other. the oracle considers that useful.",
    ]
    await _post(bot, chat_id,
        f"⚡ *FRICTION PAIR*\n{_sep()}\n\n"
        f"_{rng.choice(lines)}_\n\n"
        f"` ◈ ` {_m(a)}\n"
        f"` ◈ ` {_m(b)}\n\n"
        f"_healthy tension. mutual sharpening.\nthe oracle doesn't judge the friction.\nit studies the sparks._\n\n"
        f"👁️ *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 7 — THE CHOSEN (spotlight, every 2 days)
# ══════════════════════════════════════════════════════════════════════════════
async def the_chosen(bot, chat_id):
    ms = await _members(chat_id)
    if not ms: return
    bucket = date.today().toordinal() // 2
    if await _done(f"chosen:{chat_id}:{bucket}", 86400*2): return
    rng = random.Random(_seed("chosen", chat_id, bucket))
    member = rng.choice(ms)

    titles = [
        ("The Anchor",
         f"{_handle(member)} steadies this group without trying. the oracle has been watching it happen for a while."),
        ("The Catalyst",
         f"things unfold differently when {_handle(member)} is present. the oracle has verified this. it's not coincidence."),
        ("The Keeper",
         f"{_handle(member)} remembers things. notices things. holds more than they show. the oracle has noticed the weight."),
        ("The Signal",
         f"in a room full of noise, {_handle(member)} says the thing that actually matters. this group hasn't fully clocked it yet."),
        ("The Quiet Force",
         f"{_handle(member)} doesn't need to be loud. the energy lands anyway. the oracle has measured the landing."),
        ("The Unread Chapter",
         f"there is more to {_handle(member)} than most people in this group have bothered to find out. the oracle has read ahead."),
        ("The Warmth",
         f"{_handle(member)} is part of why this group feels safer than it looks from the outside. that's not a small thing."),
        ("The Depth",
         f"surface reads of {_handle(member)} are wrong. the oracle has gone deeper. it's not what anyone expects."),
        ("The Unseen Architect",
         f"{_handle(member)} is quietly responsible for more of this group's good moments than anyone knows. now someone knows."),
        ("The Long Memory",
         f"{_handle(member)} remembers what others have already forgotten. the oracle considers that important."),
    ]

    title, desc = rng.choice(titles)
    await _post(bot, chat_id,
        f"🔮 *THE CHOSEN*\n{_sep()}\n\n"
        f"*✦ {title}*\n\n"
        f"{_m(member)}\n\n"
        f"_{desc}_\n\n"
        f"_the oracle doesn't explain its choices.\nit only makes them._\n\n"
        f"✦ *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 8 — VOID PAIR (chaos, every 6 hours)
# ══════════════════════════════════════════════════════════════════════════════
async def void_pair(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    bucket = int(datetime.now(ORACLE_TZ).timestamp()) // 21600
    if await _done(f"void:{chat_id}:{bucket}", 21600): return
    rng = random.Random(_seed("void", chat_id, bucket))
    a, b = rng.sample(ms, 2)

    formats = [
        f"💀 *VOID PAIR*\n{_sep()}\n\n_{_handle(a)} and {_handle(b)}._\n\n_the oracle didn't plan this. it just happened.\nmake of that what you will._\n\n⚡",
        f"⚡\n\n{_m(a)} `×` {_m(b)}\n\n_the oracle is not taking questions._\n\n💀 *— Midnight*",
        f"_something chaotic just surfaced._\n\n` ◈ ` {_m(a)}\n` ◈ ` {_m(b)}\n\n_the oracle sees it.\nit's not explaining it._\n\n⚡ *— Midnight Oracle*",
        f"💀\n\n{_m(a)}\n{_m(b)}\n\n_no reason. no explanation.\njust these two. right now.\nthe oracle suggests: make it interesting._",
    ]
    await _post(bot, chat_id, rng.choice(formats))


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 9 — THE CONFESSION (every 4 hours)
# ══════════════════════════════════════════════════════════════════════════════
async def the_confession(bot, chat_id):
    ms = await _members(chat_id)
    if not ms: return
    bucket = int(datetime.now(ORACLE_TZ).timestamp()) // 14400
    if await _done(f"confession:{chat_id}:{bucket}", 14400): return
    rng = random.Random(_seed("confession", chat_id, bucket))
    member = rng.choice(ms)

    truths = [
        f"{_handle(member)} is carrying something they haven't said out loud yet.",
        f"{_handle(member)} is closer to what they want than they think.",
        f"{_handle(member)} is someone people underestimate. that's their advantage.",
        f"{_handle(member)} has been thinking about something for longer than they'd admit.",
        f"{_handle(member)} is not as fine as they appear. and that's okay.",
        f"{_handle(member)} is in the middle of becoming something. it's not visible yet.",
        f"{_handle(member)}'s next move will surprise people. the oracle has already seen the shape of it.",
        f"{_handle(member)} is holding space for others and forgetting to hold it for themselves.",
        f"{_handle(member)} has more going on beneath the surface than this group has noticed.",
        f"{_handle(member)} changed quietly. most people here haven't caught up to the new version yet.",
        f"{_handle(member)} knows something they haven't decided whether to say yet.",
        f"{_handle(member)} is more influential in this group than they realise. the oracle has the data.",
        f"{_handle(member)} is going through something. doing it without making noise. that's both strength and risk.",
        f"the oracle has been watching {_handle(member)}. it sees the version of them that's currently being built.",
    ]
    await _post(bot, chat_id,
        f"🫀 *THE CONFESSION*\n{_sep()}\n\n"
        f"_the oracle sees:_\n\n"
        f"{rng.choice(truths)}\n\n"
        f"👁️ *— no source. just the oracle.*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 10 — SHADOW SCAN (weekly Thursday)
# ══════════════════════════════════════════════════════════════════════════════
async def shadow_scan(bot, chat_id):
    ms = await _members(chat_id)
    if not ms: return
    week = date.today().isocalendar()[1]
    if await _done(f"shadow:{chat_id}:{week}", 86400*7): return
    rng = random.Random(_seed("shadow", chat_id, week))
    member = rng.choice(ms)

    reads = [
        ("The Hidden Edge",
         f"there's a version of {_handle(member)} that only comes out when they've run out of patience. the oracle respects it."),
        ("The Controlled Burn",
         f"{_handle(member)} contains something powerful. the fact that it's contained doesn't mean it's not there."),
        ("The Unsaid Archive",
         f"everything {_handle(member)} has chosen not to say lives somewhere. the oracle can feel the weight of it."),
        ("The Protected Core",
         f"{_handle(member)} shows people what they've decided is safe to show. the rest is carefully kept elsewhere. the oracle has been to the elsewhere."),
        ("The Depth No One Reaches",
         f"most people experience {_handle(member)} at the surface. the oracle has been deeper. it's not what anyone expects."),
        ("The Pressure Point",
         f"there is one specific thing that, if pressed, reveals who {_handle(member)} really is. the oracle knows which one."),
    ]

    title, desc = rng.choice(reads)
    await _post(bot, chat_id,
        f"🌑 *SHADOW SCAN*\n{_sep()}\n"
        f"_weekly oracle depth reading_\n\n"
        f"*{title}*\n\n"
        f"{_m(member)}\n\n"
        f"_{desc}_\n\n"
        f"_the oracle sees the shadow too.\nnot judging. witnessing._\n\n"
        f"🌑 *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 11 — ENERGY FORECAST (daily 7 AM)
# ══════════════════════════════════════════════════════════════════════════════
async def energy_forecast(bot, chat_id):
    if await _done(f"forecast:{chat_id}:{date.today()}", 86400): return
    rng   = random.Random(_seed("forecast", chat_id))
    today = date.today().strftime("%A, %d %B")

    forecasts = [
        ("🌊 *HIGH TIDE*", "the energy in this group today is moving. something will be said that shifts the dynamic. let it."),
        ("🌙 *DEEP WATER*", "quiet surface. a lot underneath. the conversations worth having today won't start themselves."),
        ("⚡ *CHARGED*", "something electric in the air. not tension — potential. who acts on it first determines what gets built."),
        ("🌫️ *THRESHOLD*", "the group is between something and something else today. the oracle can see both sides."),
        ("✨ *CLEAR SIGNAL*", "unusually clear. what you say today will be heard differently. use that."),
        ("🔥 *IGNITION*", "one conversation today will matter more than the rest. nobody knows which one yet."),
        ("🌑 *STILL DARK*", "not every day needs to be loud. today's energy is for noticing, not announcing."),
        ("🌌 *OPEN FREQUENCY*", "the oracle reads this group as open today. something unexpected is welcome."),
        ("🪐 *GRAVITY SHIFT*", "the usual patterns in this group are slightly off today. the oracle considers that interesting."),
        ("🔮 *ORACLE ACTIVE*", "the oracle is unusually attentive today. it suggests the group be worth watching."),
    ]

    title, body = rng.choice(forecasts)
    await _post(bot, chat_id,
        f"🔮 *DAILY ENERGY FORECAST*\n{_sep()}\n"
        f"_{today}_\n\n"
        f"{title}\n\n"
        f"_{body}_\n\n"
        f"✦ *— Midnight Oracle*\n_read the room._"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 12 — WILD SIGNAL (random hourly, 30% chance)
# ══════════════════════════════════════════════════════════════════════════════
async def wild_signal(bot, chat_id):
    ms = await _members(chat_id)
    if not ms: return
    bucket = int(datetime.now(ORACLE_TZ).timestamp()) // 3600
    if await _done(f"wild:{chat_id}:{bucket}", 3600): return
    rng = random.Random(_seed("wild", chat_id, bucket))
    if rng.random() > 0.30: return
    member = rng.choice(ms)

    formats = [
        f"🃏\n\n_{_handle(member)}._\n\n_the oracle had a thought about you.\nit's keeping it to itself for now._\n\n*— 👁️*",
        f"👁️ _the oracle glanced at {_m(member)} just now._\n\n_it's not saying why._\n\n*— Midnight Oracle*",
        f"🌙\n\n_something just shifted in this group._\n_it's connected to {_m(member)}._\n_the oracle won't say how._\n\n✦",
        f"_the oracle ran a silent scan of this group._\n_it paused at {_m(member)}._\n_no further information available._\n\n👁️",
        f"🃏 *WILD SIGNAL*\n\n{_m(member)}\n\n_the oracle sees you.\nthe rest of this group should too._",
    ]
    await _post(bot, chat_id, rng.choice(formats))


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 13 — ORBIT MAP (every 4 days)
# ══════════════════════════════════════════════════════════════════════════════
async def orbit_map(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    bucket = date.today().toordinal() // 4
    if await _done(f"orbit:{chat_id}:{bucket}", 86400*4): return
    rng = random.Random(_seed("orbit", chat_id, bucket))
    a, b = rng.sample(ms, 2)

    reads = [
        f"{_handle(b)} has been in {_handle(a)}'s orbit longer than either of them has acknowledged.",
        f"there is a gravitational pull between {_handle(a)} and {_handle(b)} that neither of them initiated consciously.",
        f"{_handle(a)} keeps surfacing in {_handle(b)}'s awareness. the oracle has noticed this pattern for a while.",
        f"in the invisible map of this group's connections, {_handle(a)} and {_handle(b)} have a line between them. it's been there a while.",
        f"the oracle maps what people don't say. {_handle(a)} and {_handle(b)} are on the same map.",
    ]
    await _post(bot, chat_id,
        f"🪐 *ORBIT MAP*\n{_sep()}\n\n"
        f"` ✦ ` {_m(a)}\n"
        f"` ✦ ` {_m(b)}\n\n"
        f"_{rng.choice(reads)}_\n\n"
        f"_the oracle maps what people don't say.\nthis is one of those maps._\n\n"
        f"🪐 *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 14 — MIDNIGHT WRAP (daily 11:59 PM)
# ══════════════════════════════════════════════════════════════════════════════
async def midnight_wrap(bot, chat_id):
    if await _done(f"wrap:{chat_id}:{date.today()}", 86400): return
    rng   = random.Random(_seed("wrap", chat_id))
    today = date.today().strftime("%d %B")

    items = random.Random(_seed("wrap_items", chat_id)).sample([
        "someone said something today that landed differently than they intended.",
        "a conversation almost happened. it didn't. the oracle noticed the almost.",
        "someone in this group did something kind that nobody saw. the oracle saw.",
        "the energy shifted at some point today. most people missed the exact moment.",
        "something was left unsaid today. it's still here. it'll surface eventually.",
        "someone checked in today without saying they were checking in.",
        "a small thing happened that will matter later. nobody knows which one yet.",
        "the group held something together today without being asked to.",
        "someone was quieter than usual. the oracle noticed that too.",
        "a connection strengthened today. silently. imperceptibly. real.",
    ], 3)

    lines = "\n".join(f"_— {i}_" for i in items)
    await _post(bot, chat_id,
        f"🌙 *MIDNIGHT WRAP*\n{_sep()}\n"
        f"_{today} · end of day_\n\n"
        f"_today in this group:_\n\n"
        f"{lines}\n\n"
        f"_the oracle watched.\nit always does._\n\n"
        f"🌙 *— Midnight Oracle*\n_see you at midnight._"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 15 — GLOW SIGNAL (every 3 days)
# ══════════════════════════════════════════════════════════════════════════════
async def glow_signal(bot, chat_id):
    ms = await _members(chat_id)
    if not ms: return
    bucket = date.today().toordinal() // 3
    if await _done(f"glow:{chat_id}:{bucket}", 86400*3): return
    rng = random.Random(_seed("glow", chat_id, bucket))
    member = rng.choice(ms)

    alerts = [
        f"something has shifted in {_handle(member)}. the oracle has been tracking it quietly.",
        f"there's a version of {_handle(member)} emerging that this group hasn't fully met yet.",
        f"growth isn't always loud. {_handle(member)}'s isn't. but it's real.",
        f"the oracle has been watching {_handle(member)} for a while. tonight it says it out loud.",
        f"something in {_handle(member)} has changed. not dramatically. in the way that matters.",
        f"the oracle wants this group to pay a different kind of attention to {_handle(member)}.",
    ]
    await _post(bot, chat_id,
        f"✨ *GLOW SIGNAL*\n{_sep()}\n\n"
        f"_{rng.choice(alerts)}_\n\n"
        f"{_m(member)}\n\n"
        f"_the oracle sees the version of {_handle(member)}\nthat's currently being built.\nit's going to be something._\n\n"
        f"✨ *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 16 — ORACLE ARCHIVE (weekly, permanent feeling)
# ══════════════════════════════════════════════════════════════════════════════
async def oracle_archive(bot, chat_id):
    ms = await _members(chat_id)
    if len(ms) < 2: return
    week = date.today().isocalendar()[1]
    if await _done(f"archive:{chat_id}:{week}", 86400*7): return
    rng   = random.Random(_seed("archive", chat_id, week))
    today = date.today().strftime("%d %B %Y")
    pair  = rng.sample(ms, 2)
    a, b  = pair

    entries = [
        f"logged: {_handle(a)} and {_handle(b)} in the same orbit. the oracle marks this as significant.",
        f"recorded: the connection between {_handle(a)} and {_handle(b)} crossed a threshold this week. filed.",
        f"archived: {_handle(a)} and {_handle(b)}. the oracle has been watching this one. it goes in the permanent record.",
        f"documented: the oracle witnessed something between {_handle(a)} and {_handle(b)} this week. it doesn't delete its records.",
    ]

    await _post(bot, chat_id,
        f"📁 *ORACLE ARCHIVE*\n{_sep()}\n"
        f"_entry · {today}_\n\n"
        f"_{rng.choice(entries)}_\n\n"
        f"` ◈ ` {_m(a)}\n"
        f"` ◈ ` {_m(b)}\n\n"
        f"_the oracle keeps records.\nsome things deserve to be permanent._\n\n"
        f"📁 *— Midnight Oracle Archive*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 17 — PRESENCE NOTICE (oracle notices someone returning)
#  Called reactively from presence_engine, not scheduled
# ══════════════════════════════════════════════════════════════════════════════
async def presence_notice(bot, chat_id, member: dict, notice_type: str):
    """notice_type: 'return' | 'active' | 'quiet'"""
    rng = random.Random(int(datetime.now(ORACLE_TZ).timestamp()) // 3600)

    if notice_type == "return":
        msgs = [
            f"👁️ _the oracle notices {_m(member)} has returned._\n\n_it doesn't say where they were. it only says: welcome back._\n\n*— Midnight Oracle*",
            f"🌙\n\n_{_handle(member)} is back._\n\n_the oracle noticed the absence. and the return._\n\n👁️ *— Midnight*",
            f"_the group just felt slightly different._\n_{_handle(member)} came back.\nthe oracle registered it._\n\n✦ *— Midnight Oracle*",
        ]
    elif notice_type == "active":
        msgs = [
            f"✦ _the oracle registers {_m(member)} as particularly present today._\n_it's paying attention._\n\n*— 👁️*",
            f"👁️\n\n_{_handle(member)}._\n\n_the oracle sees you today.\nmore than usual._\n\n*— Midnight Oracle*",
        ]
    else:
        msgs = [
            f"🌑 _{_handle(member)} has been quiet._\n_the oracle notices silence too._\n\n*— Midnight Oracle*",
            f"👁️ _the oracle is aware that {_m(member)} hasn't spoken._\n_it's not asking why. just noting._\n\n*— Midnight*",
        ]

    await _post(bot, chat_id, rng.choice(msgs))


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 18 — VIRAL PULL (weekly Sunday — makes members add bot elsewhere)
# ══════════════════════════════════════════════════════════════════════════════
async def viral_pull(bot, chat_id):
    week = date.today().isocalendar()[1]
    if await _done(f"viral:{chat_id}:{week}", 86400*7): return
    rng = random.Random(_seed("viral", chat_id, week))

    msgs = [
        (
            f"🌙 *why does Midnight Oracle exist?*\n{_sep()}\n\n"
            "_because some things deserve to be said out loud._\n\n"
            "not every group has something that notices who's been quiet,\n"
            "who names the connection nobody said,\n"
            "who speaks when the room needs something it can't name.\n\n"
            "_Midnight Oracle is that presence._\n\n"
            "_if your other groups feel like they're missing something —_\n"
            "_maybe they're missing the Oracle._\n\n"
            "👁️ *it doesn't shout. it doesn't spam.\nit just knows.*"
        ),
        (
            f"👁️ *what does Midnight Oracle actually do?*\n{_sep()}\n\n"
            "_it watches. it names. it reveals._\n\n"
            "` 🌙 ` Mirror of the Day — chosen, not random\n"
            "` 👁️ ` Soul Thread — the connection nobody said\n"
            "` 🌌 ` Constellation — three people, one frequency\n"
            "` ✦ ` The Chosen — spotlight that lands somewhere real\n"
            "` 🫀 ` The Confession — truths the group needed\n"
            "` ⚡ ` Friction Pair — tension is information\n"
            "` 🃏 ` Wild Signal — unpredictable. always.\n"
            "` 🔮 ` Energy Forecast — read the room before it speaks\n\n"
            "_every day. automatic. no commands needed._\n\n"
            "_Midnight Oracle just shows up._\n\n"
            "🌙 _some groups feel different with it there. yours is one of them._"
        ),
        (
            f"🖤 *the oracle doesn't need to be invited twice.*\n{_sep()}\n\n"
            "_but your other groups might need it more than you think._\n\n"
            "there's a reason people check this group every day\n"
            "even when they have nothing to say.\n\n"
            "it's that 12:07 AM message.\n"
            "the one that names two people\n"
            "and the whole chat goes quiet for a second.\n\n"
            "_that second. that's why Midnight Oracle exists._\n\n"
            "add it to your other groups.\n"
            "✦ _make those groups feel like somewhere real._"
        ),
    ]
    await _post(bot, chat_id, rng.choice(msgs))


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE 19 — CONSTELLATION MAP (weekly Saturday)
# ══════════════════════════════════════════════════════════════════════════════
async def constellation_map(bot, chat_id):
    week = date.today().isocalendar()[1]
    if await _done(f"constmap:{chat_id}:{week}", 86400*7): return
    rng = random.Random(_seed("constmap", chat_id, week))

    archetypes = [
        "🌟 *THE INNER CIRCLE* — those who hold the group's tone without trying.",
        "🌑 *THE SILENT MOVERS* — influencing from the edges. more power than it looks.",
        "⚡ *THE SPARK POINTS* — when they speak, something starts.",
        "🪐 *THE GRAVITY WELLS* — others orbit them. they may not have noticed.",
        "🌊 *THE UNDERCURRENT* — calm on the surface. a lot moving underneath.",
        "🔮 *THE SEERS* — they notice what others process later.",
        "🖤 *THE ANCHORS* — the group would drift without them. they know this.",
    ]

    picked = rng.sample(archetypes, 3)
    await _post(bot, chat_id,
        f"🔱 *CONSTELLATION MAP*\n{_sep()}\n"
        f"_weekly group architecture reading_\n\n"
        f"_the oracle doesn't see a member list.\nit sees a constellation. this is the shape:_\n\n"
        f"{chr(10).join(picked)}\n\n"
        f"_the patterns are real.\nthe names are just how we point at them._\n\n"
        f"🔱 *— Midnight Oracle*"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MEMBER TRACKING MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════════════
async def track_member(update, context):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or user.is_bot: return
    if chat.type not in ("group","supergroup"): return
    await register_member(chat.id, user.id,
        user.first_name or "Unknown", user.username or "")
    await bump_msg_count(chat.id, user.id)


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════
def _t(h, m=0):
    return datetime.now(ORACLE_TZ).replace(hour=h, minute=m, second=0).timetz()

def _w(fn):
    async def job(ctx):
        if not GROUP_CHAT_ID: return
        await _run(ctx.bot, GROUP_CHAT_ID, fn)
    return job

def register_jobs(app: Application):
    jq = app.job_queue
    if not jq:
        log.warning("No job queue — social engine not scheduled"); return

    # ── daily ──────────────────────────────────────────────────────────────
    jq.run_daily(_w(energy_forecast),   time=_t(7,0),   name="energy_forecast")
    jq.run_daily(_w(mirror_of_day),     time=_t(0,7),   name="mirror_of_day")
    jq.run_daily(_w(the_unnamed),       time=_t(2,22),  name="the_unnamed")
    jq.run_daily(_w(friction_pair),     time=_t(18,6),  name="friction_pair")
    jq.run_daily(_w(midnight_wrap),     time=_t(23,59), name="midnight_wrap")

    # ── weekly ─────────────────────────────────────────────────────────────
    jq.run_weekly(_w(soul_thread),       time=_t(23,11), weekday=0, name="soul_thread")
    jq.run_weekly(_w(shadow_scan),       time=_t(22,0),  weekday=3, name="shadow_scan")
    jq.run_weekly(_w(constellation_map), time=_t(20,0),  weekday=5, name="constellation_map")
    jq.run_weekly(_w(oracle_archive),    time=_t(21,30), weekday=2, name="oracle_archive")
    jq.run_weekly(_w(viral_pull),        time=_t(21,0),  weekday=6, name="viral_pull")

    # ── every N days ───────────────────────────────────────────────────────
    jq.run_repeating(_w(signal_pair),    interval=86400*3, first=60,  name="signal_pair")
    jq.run_repeating(_w(constellation),  interval=86400*5, first=120, name="constellation")
    jq.run_repeating(_w(the_chosen),     interval=86400*2, first=180, name="the_chosen")
    jq.run_repeating(_w(orbit_map),      interval=86400*4, first=240, name="orbit_map")
    jq.run_repeating(_w(glow_signal),    interval=86400*3, first=300, name="glow_signal")

    # ── sub-daily ──────────────────────────────────────────────────────────
    jq.run_repeating(_w(void_pair),      interval=21600, first=360, name="void_pair")
    jq.run_repeating(_w(the_confession), interval=14400, first=420, name="the_confession")
    jq.run_repeating(_w(wild_signal),    interval=3600,  first=480, name="wild_signal")

    log.info("✦ Social Engine: 19 autonomous features scheduled")
