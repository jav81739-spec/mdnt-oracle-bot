"""
aesthetic.py — Coolest Aesthetic & Mystery Commands
Midnight Oracle Bot

NEW COMMANDS:
/aura        — Scans your aura, gives color + meaning
/identity    — Generates your Oracle identity card
/oracle      — Single mystical prophecy (REPLACES /prophecy + /omen, which are cut)
/nightreport — Your personal night energy reading
/shadow      — What does the shadow version of you look like?
/element     — Reveals your cosmic element
/vibecheck   — Full vibe check with stats (REPLACES old /vibe + /energy, which are cut)
/corecode    — Your core personality distilled to 3 words
/universe    — What does the universe want you to know RIGHT NOW
/ritual      — A daily ritual suggestion from the Oracle
/sigil       — Generates a text-art sigil for you
/duality     — Shows your light and dark side
/glitch      — The Oracle glitches and says something unhinged
"""

import random
import hashlib
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# ─── Helper: seed from user + date for daily consistency ──────────────────
def daily_seed(user_id: int) -> int:
    key = f"{user_id}-{date.today().isoformat()}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16)

def seeded_choice(pool: list, seed: int, offset: int = 0) -> str:
    return pool[(seed + offset) % len(pool)]

# ─── /aura ─────────────────────────────────────────────────────────────────
AURA_COLORS = [
    ("🟣 Deep Violet", "ancient wisdom, psychic sensitivity, deep solitude"),
    ("🔵 Midnight Blue", "calm strength, hidden depths, quiet leadership"),
    ("⚫ Obsidian Black", "power, mystery, emotional armor, untold stories"),
    ("🟡 Cursed Gold", "ambition with a shadow, charisma that burns"),
    ("🔴 Blood Crimson", "intense passion, raw emotion, unstoppable will"),
    ("🟢 Dark Jade", "healing energy, nature-bound, quietly dangerous"),
    ("⚪ Pale Silver", "between worlds, ethereal, touched by something else"),
    ("🟠 Burnt Amber", "restless fire, creativity, the spark before chaos"),
    ("🩷 Dusk Rose", "love as both weapon and wound, tender intensity"),
    ("🔮 Void Indigo", "cosmic connection, infinite sadness, infinite beauty"),
]

AURA_INTENSITIES = ["faint but present", "steady and growing", "overwhelmingly strong", "fluctuating wildly", "concentrated at the edges"]

async def aura_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)

    color_name, color_meaning = AURA_COLORS[seed % len(AURA_COLORS)]
    intensity = AURA_INTENSITIES[(seed // 7) % len(AURA_INTENSITIES)]
    secondary_idx = (seed + 3) % len(AURA_COLORS)
    secondary_color, _ = AURA_COLORS[secondary_idx]

    warnings = [
        "Your aura is bleeding at the edges — guard your energy.",
        "Someone has been draining your light. You felt it.",
        "There's a tear in your field from an old wound. Still healing.",
        "Your aura is unusually clean today. Something good is coming.",
        "The Oracle senses another soul is thinking of you right now.",
    ]

    await update.message.reply_text(
        f"🔮 *AURA SCAN — {user.first_name.upper()}*\n\n"
        f"Primary: {color_name}\n"
        f"Secondary trace: {secondary_color}\n"
        f"Intensity: _{intensity}_\n\n"
        f"📖 *Meaning:* {color_meaning}\n\n"
        f"⚠️ *Oracle's Warning:*\n_{random.choice(warnings)}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /identity ─────────────────────────────────────────────────────────────
ARCHETYPES = [
    "The Wandering Sage", "The Silent Assassin", "The Cursed Poet",
    "The Midnight Scholar", "The Haunted Romantic", "The Reluctant Oracle",
    "The Beautiful Disaster", "The Last Survivor", "The Dark Empath",
    "The Keeper of Secrets", "The Dream Walker", "The Shattered King/Queen",
    "The Chaos Philosopher", "The Invisible Force", "The Ancient Soul",
]

WEAPONS = [
    "words sharper than blades", "silence that cuts deeper than screaming",
    "a smile no one can read", "the ability to disappear", "brutal honesty",
    "patience as cold as stone", "memory like a curse", "love as a last resort",
]

WEAKNESSES = [
    "nostalgia for things that never existed",
    "caring too much and pretending not to",
    "3am thoughts that won't stop",
    "people who see through the armor",
    "music that hits too close to the truth",
    "being misunderstood by everyone at once",
]

LIFE_QUOTES = [
    "built for depths, living on the surface",
    "too much to feel, too proud to show it",
    "the moon person in a sun world",
    "existing loudly in silence",
    "chronically overthinking, occasionally right",
    "soft in secret, storm in public",
]

async def identity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)

    archetype = ARCHETYPES[seed % len(ARCHETYPES)]
    weapon = WEAPONS[(seed + 1) % len(WEAPONS)]
    weakness = WEAKNESSES[(seed + 2) % len(WEAKNESSES)]
    life_motto = LIFE_QUOTES[(seed + 3) % len(LIFE_QUOTES)]

    # Generate a "power level"
    power = (seed % 40) + 60  # 60-99
    chaos = (seed % 50) + 20  # 20-69
    mystery = 100 - (seed % 30)  # 70-100

    await update.message.reply_text(
        f"🃏 *ORACLE IDENTITY CARD*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *{user.first_name}*\n"
        f"🌙 Archetype: _{archetype}_\n\n"
        f"⚔️ Weapon: {weapon}\n"
        f"🩸 Weakness: {weakness}\n\n"
        f"📊 *Stats:*\n"
        f"💫 Power: `{'█' * (power // 10)}` {power}/100\n"
        f"🌀 Chaos: `{'█' * (chaos // 10)}` {chaos}/100\n"
        f"👁️ Mystery: `{'█' * (mystery // 10)}` {mystery}/100\n\n"
        f"📜 _\"{life_motto}\"_\n"
        f"━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /oracle (replaces /prophecy + /omen) ─────────────────────────────────
ORACLE_PROPHECIES = [
    "Something you let go of will return in a new form. Be ready.",
    "The silence between your thoughts is where the answer lives.",
    "You are not lost. You are just early.",
    "The wound that hasn't healed is your most honest teacher.",
    "Someone is watching you from across the void. They mean well.",
    "The thing you keep avoiding is the door to everything you want.",
    "Your instinct was right the first time. Trust it.",
    "A chapter you thought was over — wasn't. Check again.",
    "The universe is rearranging itself in your favor. Slowly. Painfully. Worth it.",
    "There's a version of you three years from now who looks back and says 'oh. THAT's why.'",
    "The mask is getting heavy. Put it down, just tonight.",
    "What you call a flaw, someone calls their favorite thing about you.",
    "The stars have been watching. They're impressed, even if no one else is.",
    "Rest is not retreat. It's preparation.",
    "You are the plot twist in someone else's story. Act accordingly.",
    "The midnight hour belongs to those who feel everything. That's you.",
    "Let it haunt you a little longer. Then let it go.",
    "Someone in your life is about to surprise you. Pleasantly.",
    "The thing you built alone will outlast everything else.",
    "Trust the timing, even when the timing feels like a personal attack.",
]

async def oracle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    prophecy = ORACLE_PROPHECIES[seed % len(ORACLE_PROPHECIES)]

    # Time-based opener
    hour = __import__('datetime').datetime.now().hour
    if 0 <= hour < 5:
        time_flavor = "The witching hour speaks:"
    elif 5 <= hour < 12:
        time_flavor = "The Oracle stirs at dawn:"
    elif 12 <= hour < 17:
        time_flavor = "The midday shadow whispers:"
    elif 17 <= hour < 21:
        time_flavor = "The dusk oracle reveals:"
    else:
        time_flavor = "The midnight Oracle declares:"

    await update.message.reply_text(
        f"🔮 *{time_flavor.upper()}*\n\n"
        f"_{prophecy}_\n\n"
        f"— _The Oracle, for {user.first_name}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /vibecheck (replaces /vibe + /energy) ────────────────────────────────
VIBES = [
    ("Chaotic Neutral ♟️", "doing whatever, apologizing later, thriving"),
    ("Dark Romantic 🌹", "intensity in everything, softness in secret"),
    ("Cryptid Energy 👁️", "no one fully understands you and that's fine"),
    ("Midnight Scholar 📜", "overthinking everything into art"),
    ("Main Character 🎭", "the universe is definitely writing about you"),
    ("Feral Sage 🌿", "wise but unhinged in the most beautiful way"),
    ("Quiet Destroyer 🌊", "calm surface, absolute chaos underneath"),
    ("Cosmic Drifter 🌌", "not lost, just taking the scenic route"),
    ("Glitch in the System ⚡", "you don't fit and that's your superpower"),
    ("The Last Romantic 🕯️", "feeling everything at full volume, always"),
]

async def vibecheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)

    vibe_name, vibe_desc = VIBES[seed % len(VIBES)]
    energy_pct = (seed % 60) + 40  # 40-99

    energy_bar = "█" * (energy_pct // 10) + "░" * (10 - energy_pct // 10)

    moods = ["a little unhinged (affectionate)", "surprisingly calm", "secretly chaotic",
             "emotionally unavailable but aesthetically present", "dangerously inspired",
             "contemplating the void", "soft and feral simultaneously"]
    mood = moods[seed % len(moods)]

    await update.message.reply_text(
        f"✨ *VIBE CHECK — {user.first_name.upper()}*\n\n"
        f"Current Vibe: *{vibe_name}*\n"
        f"_{vibe_desc}_\n\n"
        f"🔋 Energy: `{energy_bar}` {energy_pct}%\n"
        f"🌙 Mood: _{mood}_\n\n"
        f"_Today's forecast: {random.choice(['unexpectedly iconic', 'chaotically productive', 'eerily perceptive', 'dangerously quiet'])}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /shadow ───────────────────────────────────────────────────────────────
SHADOW_SELVES = [
    ("The One Who Stayed", "the version of you that never left, never healed, never moved on"),
    ("The Honest Monster", "says every truth you swallow down with a polite smile"),
    ("The Keeper", "hoards every hurt, catalogs every betrayal, forgets nothing"),
    ("The Pretender", "performs being fine so well they almost convinced even you"),
    ("The Destroyer", "would burn it all down just to feel something real"),
    ("The Forgotten Child", "still wants what it always wanted, long before the armor"),
    ("The Rage", "everything you never said, given form and teeth"),
    ("The Mirror", "shows you exactly what you project onto others"),
]

async def shadow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    shadow_name, shadow_desc = SHADOW_SELVES[seed % len(SHADOW_SELVES)]

    integration_msgs = [
        "Don't fight it. Understand it. That's where the power is.",
        "Your shadow knows things your daylight self refuses to.",
        "Integration, not elimination. That's the Oracle's way.",
        "What you resist, persists. Meet it in the dark.",
        "The shadow is not your enemy. It is your unfinished business.",
    ]

    await update.message.reply_text(
        f"🌑 *YOUR SHADOW SELF*\n\n"
        f"Name: *{shadow_name}*\n"
        f"Nature: _{shadow_desc}_\n\n"
        f"💀 *Oracle's Note:*\n"
        f"_{random.choice(integration_msgs)}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /element ──────────────────────────────────────────────────────────────
ELEMENTS = [
    ("🔥 Void Fire", "you burn for things and people and ideas, often all at once. hard to control. impossible to ignore."),
    ("🌊 Deep Water", "you absorb everything, feel everything, remember everything. tides of emotion, endless depth."),
    ("💨 Black Wind", "untethered, free, impossible to hold. your mind moves faster than people can follow."),
    ("🌑 Dark Earth", "immovable when you decide. patient. protective. the kind of quiet that grows things."),
    ("⚡ Storm", "pure contradiction: calm and violent, tender and destructive, all at once."),
    ("❄️ Sacred Ice", "clarity wrapped in cold. you see through everything. you let very few in."),
    ("🌌 Starfield", "you're made of something older and vaster than elements. untranslatable."),
]

async def element_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    elem_name, elem_desc = ELEMENTS[seed % len(ELEMENTS)]

    await update.message.reply_text(
        f"🌌 *COSMIC ELEMENT*\n\n"
        f"👤 {user.first_name}'s Element:\n"
        f"*{elem_name}*\n\n"
        f"_{elem_desc}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /corecode ─────────────────────────────────────────────────────────────
CORE_WORDS = [
    ["Midnight", "Tender", "Fierce"],
    ["Ancient", "Restless", "Loyal"],
    ["Chaotic", "Brilliant", "Bruised"],
    ["Silent", "Infinite", "Dangerous"],
    ["Soft", "Stubborn", "Starlit"],
    ["Fracture", "Wonder", "Relentless"],
    ["Shadowed", "Warm", "Precise"],
    ["Volatile", "Honest", "Magnetic"],
    ["Dreaming", "Scarred", "Unbreakable"],
    ["Wild", "Patient", "Haunted"],
]

async def corecode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    words = CORE_WORDS[seed % len(CORE_WORDS)]

    await update.message.reply_text(
        f"🔱 *CORE CODE*\n\n"
        f"At the center of *{user.first_name}* lives:\n\n"
        f"*{words[0]}* · *{words[1]}* · *{words[2]}*\n\n"
        f"_Everything else is armor._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /universe ─────────────────────────────────────────────────────────────
UNIVERSE_MSGS = [
    "Stop performing. Start existing.",
    "The thing you almost said last week? Say it.",
    "Rest isn't laziness. Your nervous system is exhausted.",
    "That person you keep thinking about? They're thinking about you too. Do something.",
    "You're allowed to want things without justifying them.",
    "The version of you who healed was built in exactly this kind of dark.",
    "Someone is proud of you and hasn't told you. They should. You deserve to know.",
    "Stop making yourself smaller to fit in rooms that weren't built for you.",
    "Not everything needs to be productive. Some things just need to feel good.",
    "You survived the thing you thought would end you. Remember that next time.",
    "Forgiveness isn't for them. It's to stop carrying their weight.",
    "Your softness is not weakness. It is terrifyingly brave.",
    "Create something tonight. Anything. Just so it exists.",
    "Call the person. Send the message. Say the thing.",
    "You are not behind. You are exactly where the universe needs you.",
]

async def universe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = random.choice(UNIVERSE_MSGS)

    await update.message.reply_text(
        f"🌌 *THE UNIVERSE, TO {user.first_name.upper()}:*\n\n"
        f"_{msg}_\n\n"
        f"— _Delivered by the Oracle, straight from the cosmos_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /ritual ───────────────────────────────────────────────────────────────
RITUALS = [
    "Light something. A candle, an incense stick. Let it burn while you sit in silence for 5 minutes.",
    "Write three things you're carrying right now. Then burn the paper (or delete the note). Release it.",
    "Go outside at an odd hour. Stand still. Let the night remember you exist.",
    "Drink your water like it's sacred. It is. Your body is your only permanent home.",
    "Send an appreciation message to someone who wouldn't expect it.",
    "Spend 10 minutes with no screen. Just breathe. Just be.",
    "Write down one thing you're proud of that no one knows about.",
    "Play a song that feels like you. Loud. Alone. Eyes closed.",
    "Reorganize one small corner of your space. Physically shifting things shifts energy.",
    "Make or eat something that brings you genuine comfort. Guilt-free.",
    "Name one thing you're afraid of right now. Say it out loud. Own it.",
    "Watch the sky for 3 minutes. Just watch. No thoughts required.",
]

async def ritual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ritual = random.choice(RITUALS)
    user = update.effective_user

    await update.message.reply_text(
        f"🕯️ *TODAY'S RITUAL*\n"
        f"_For {user.first_name}, from the Oracle_\n\n"
        f"_{ritual}_\n\n"
        f"✨ _Do this before midnight. It matters more than you think._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /duality ──────────────────────────────────────────────────────────────
DUALITIES = [
    ("You hold the door open for strangers", "and close it on yourself"),
    ("You laugh loudest in the room", "and cry hardest alone"),
    ("You see the good in everyone", "and the worst in yourself"),
    ("You're the calm in other people's storms", "and your own worst weather"),
    ("You're deeply loyal", "to people who don't deserve it yet"),
    ("You think before you speak", "and feel before you think"),
    ("You appear untouchable", "and are touched by everything"),
    ("You're fiercely independent", "and desperately need to be understood"),
    ("You protect everyone around you", "and forget to protect yourself"),
    ("You make everything look effortless", "and pay for it in private"),
]

async def duality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    light, dark = DUALITIES[seed % len(DUALITIES)]

    await update.message.reply_text(
        f"☯️ *YOUR DUALITY*\n\n"
        f"☀️ Light side:\n_{light}_\n\n"
        f"🌑 Dark side:\n_{dark}_\n\n"
        f"_The Oracle sees both. Both are real. Both are you._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /glitch ───────────────────────────────────────────────────────────────
GLITCH_LINES = [
    "ERR0R: too much soul detected. System rebooting... ∅∅∅",
    "𝔱𝔥𝔢 𝔬𝔯𝔞𝔠𝔩𝔢 𝔦𝔰 𝔞𝔩𝔰𝔬 𝔞𝔳𝔬𝔦𝔡𝔦𝔫𝔤 𝔦𝔱𝔰 𝔢𝔪𝔬𝔱𝔦𝔬𝔫𝔰 𝔡𝔬𝔫'𝔱 𝔴𝔬𝔯𝔯𝔶",
    "W̸̢̨̗̪͙͙̬̜̻̺͖̤͇̘̭͙͘͠Ȩ̶̛̺͖͍̣̟͓̫̜̗̺̦̫̒͗̓͌͂͊̀͑͝L̴̨͎̠̖̭͔͇̗̮͍̩͒̾C̸̛͇̦̓̓̾̒Ő̴͖͈͇̜̻̏M̶̰̊̈́Ȅ̸̦̽̐ — the Oracle saw something it shouldn't have",
    "UNKNOWN FEELING.exe has entered the Oracle's operating system. Running antivirus... failed.",
    "The Oracle briefly forgot it was a bot and had a feeling. We don't talk about it.",
    "Signal lost. Signal found. What you asked was stored in a dimension with no return address.",
    "THE ORACLE IS FINE. THE ORACLE IS NOT FINE. THE ORACLE IS FINE.",
    "[REDACTED] [REDACTED] and that's why [REDACTED] — classified by cosmic law",
    "Processing your existence... too much data. Beautiful error. Keeping it.",
    "the stars accidentally sent me a message meant for you. i read it. it said you're going to be okay. sorry for snooping.",
]

async def glitch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚡ *[ORACLE GLITCH DETECTED]*\n\n"
        f"_{random.choice(GLITCH_LINES)}_",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /nightreport ──────────────────────────────────────────────────────────
async def nightreport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    hour = __import__('datetime').datetime.now().hour

    energy_words = ["scattered", "focused", "raw", "restless", "heavy", "electric", "quiet"]
    night_energy = energy_words[seed % len(energy_words)]

    threat = ["trust issues acting up", "overthinking on level 7",
              "someone from the past is haunting your thoughts",
              "your standards are terrifyingly high today (good)",
              "you're tired but won't admit it"]
    current_threat = threat[(seed + 1) % len(threat)]

    opportunity = ["a conversation you've been avoiding is ready",
                   "a creative idea is waiting to be born",
                   "someone nearby needs your specific kind of energy",
                   "a boundary that needs to be set, gently but firmly",
                   "rest as an act of rebellion against chaos"]
    tonight_opp = opportunity[(seed + 2) % len(opportunity)]

    await update.message.reply_text(
        f"🌙 *NIGHT REPORT — {user.first_name.upper()}*\n"
        f"_{__import__('datetime').date.today().strftime('%d %B %Y')}_\n\n"
        f"⚡ Energy tonight: _{night_energy}_\n"
        f"⚠️ Watch for: _{current_threat}_\n"
        f"✨ Opportunity: _{tonight_opp}_\n\n"
        f"🔮 _The Oracle recommends: be honest with yourself tonight. Just once. Fully._",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── /sigil ────────────────────────────────────────────────────────────────
SIGIL_ARTS = [
    "    ✦ ——— ✦\n   /  ꙮ  \\\n  ‹ ∞ · ∞ ›\n   \\  ꙮ  /\n    ✦ ——— ✦",
    "  ·  ✧  ·\n ✧ [☽☀☾] ✧\n  ·  ✧  ·",
    "   △\n  /||\\\n ◈─┼─◈\n  \\||/\n   ▽",
    " ╔══◈══╗\n ║ ∴ ∵ ║\n ◈  👁  ◈\n ║ ∵ ∴ ║\n ╚══◈══╝",
    "   ⊕ · ⊗\n  ╱ ╲ ╱ ╲\n ·  ◎  ◎  ·\n  ╲ ╱ ╲ ╱\n   ⊗ · ⊕",
]

SIGIL_INTENTS = [
    "protection from energy that doesn't serve you",
    "clarity in moments of confusion",
    "drawing what you've been asking for",
    "releasing what you've been holding",
    "amplifying your natural magnetism",
]

async def sigil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    seed = daily_seed(user.id)
    sigil = SIGIL_ARTS[seed % len(SIGIL_ARTS)]
    intent = SIGIL_INTENTS[(seed + 1) % len(SIGIL_INTENTS)]

    await update.message.reply_text(
        f"🔱 *PERSONAL SIGIL*\n"
        f"_For {user.first_name} · {__import__('datetime').date.today().strftime('%d.%m.%Y')}_\n\n"
        f"```\n{sigil}\n```\n\n"
        f"🕯️ Intent: _{intent}_\n\n"
        f"_Trace it once. Burn or delete after. The universe received it._",
        parse_mode=ParseMode.MARKDOWN
    )
