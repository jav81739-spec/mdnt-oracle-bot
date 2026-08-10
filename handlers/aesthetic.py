import random
from telegram import Update
from telegram.ext import ContextTypes
from handlers.mentions import mention

ORACLE_LINES = [
    "The answer lies where you least expect it...",
    "Not yet. But soon, the fog will clear.",
    "What you seek is already seeking you.",
    "Silence holds the truth you're avoiding.",
]

TAROT_CARDS = [
    ("The Fool 🃏", "New beginnings await — leap without fear."),
    ("The Moon 🌙", "Nothing is quite as it seems tonight."),
    ("The Star ⭐", "Hope returns after the storm."),
    ("The Tower 🗼", "Something is about to break — and that's okay."),
]

AURA_COLORS = [
    ("Violet 💜", "mysterious and deep — you see what others miss"),
    ("Crimson ❤️‍🔥", "intense energy — you burn bright in every room"),
    ("Silver 🩶", "calm and unreadable — a quiet storm"),
    ("Gold 💛", "magnetic — people are drawn to you without knowing why"),
]

FATE_LINES = [
    "Today favors those who stay quiet and watch.",
    "A message you're waiting for arrives sooner than expected.",
    "Avoid decisions made before noon.",
    "Someone from your past resurfaces — let them.",
]

LORE_TEMPLATES = [
    "Legend says this group was born under a blood moon, and every message since has echoed through the void 🌑",
    "They say the founder of this chat once bargained with silence itself just to keep the group alive 🕯️",
    "In the old texts, it is written: this group shall never truly sleep, only whisper 👁️",
]

STARSIGNS = {
    "aries": "Fire and impatience — you move before you think, and it usually works out.",
    "taurus": "Grounded and stubborn — once you decide, the universe better keep up.",
    "gemini": "Two minds in one body — restless, curious, impossible to predict.",
    "cancer": "Guarded but deep — you feel everything, you just don't always show it.",
    "leo": "Magnetic and proud — the room notices when you walk in.",
    "virgo": "Precise and quietly powerful — chaos bends around your order.",
    "libra": "Balance-seeking — you'd rather lose a little than break the peace.",
    "scorpio": "Intense and private — few really know what's underneath.",
    "sagittarius": "Free and blunt — you say what others are afraid to.",
    "capricorn": "Patient and ambitious — you're playing a longer game than most.",
    "aquarius": "Detached and visionary — you live slightly ahead of everyone else.",
    "pisces": "Dreamy and absorbent — you carry the moods of the room.",
}

EMOJI_AURAS = ["🌊😌", "🔥😤", "🌙🥱", "⚡😏", "🍃😇", "🖤😈", "✨🥹"]


async def oracle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args) if context.args else "your question"
    await update.message.reply_text(f"🔮 *The Oracle speaks on \"{question}\":*\n\n_{random.choice(ORACLE_LINES)}_", parse_mode="Markdown")
    from handlers.chat import send_mood_gif
    await send_mood_gif(context.bot, update.effective_chat.id, "mystical crystal ball")


async def tarot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card, meaning = random.choice(TAROT_CARDS)
    await update.message.reply_text(f"🃏 You drew: *{card}*\n\n_{meaning}_", parse_mode="Markdown")
    from handlers.chat import send_mood_gif
    await send_mood_gif(context.bot, update.effective_chat.id, "tarot cards mystical")


async def aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    color, vibe = random.choice(AURA_COLORS)
    await update.message.reply_text(f"✨ {mention(target.id, target.first_name)}'s aura is *{color}*\n_{vibe}_", parse_mode="Markdown")


async def fate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🕯️ *Today's fate:*\n\n_{random.choice(FATE_LINES)}_", parse_mode="Markdown")


async def whisper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Usage: reply to someone's message with /whisper [your secret text]")
        return
    target = update.message.reply_to_message.from_user
    text = " ".join(context.args)
    try:
        await context.bot.send_message(target.id, f"👁️ A whisper from the group:\n\n{text}")
        await update.message.reply_text(f"👁️ Someone whispered to {target.first_name}...")
    except Exception:
        await update.message.reply_text(
            f"Couldn't deliver — {target.first_name} needs to have started a DM with me first."
        )
    try:
        await update.message.delete()
    except Exception:
        pass


async def lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 {random.choice(LORE_TEMPLATES)}")


async def starsign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /starsign [sign] — e.g. /starsign scorpio")
        return
    sign = context.args[0].lower()
    meaning = STARSIGNS.get(sign)
    if not meaning:
        await update.message.reply_text("Unknown sign. Try: aries, taurus, gemini, cancer, leo, virgo, libra, scorpio, sagittarius, capricorn, aquarius, pisces")
        return
    await update.message.reply_text(f"🌌 *{sign.title()}*\n\n_{meaning}_", parse_mode="Markdown")


async def emoji_aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"{mention(target.id, target.first_name)}'s energy reading: {random.choice(EMOJI_AURAS)}",
        parse_mode="Markdown",
    )


async def confess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anonymous confession — bot posts it, identity is not shown in the group."""
    if not context.args:
        await update.message.reply_text("Usage: /confess your secret text")
        return
    confession_text = " ".join(context.args)
    try:
        await update.message.delete()  # remove the original so identity isn't in chat history
    except Exception:
        pass
    await context.bot.send_message(
        update.effective_chat.id,
        f"🕯️ *Anonymous confession:*\n\n{confession_text}",
        parse_mode="Markdown",
    )


MOOD_WORDS = ["ethereal", "feral", "unbothered", "nostalgic", "restless", "soft", "chaotic-good", "hazy"]
MOOD_EMOJIS = ["🌫️", "🖤", "✨", "🌙", "🍂", "🕯️", "🌊", "⚡"]

DREAM_INTERPRETATIONS = [
    "This dream reflects a part of you seeking control you don't have right now.",
    "This suggests unfinished business with someone from your past.",
    "This is your mind processing a change you haven't fully accepted yet.",
    "This points to a desire for freedom from something weighing on you.",
]

MANIFEST_TEMPLATE = "✨ It is done. {text} — the universe has heard you. ✨"


async def moodboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = random.sample(MOOD_WORDS, 3)
    emojis = random.sample(MOOD_EMOJIS, 3)
    combo = " · ".join(f"{w} {e}" for w, e in zip(words, emojis))
    await update.message.reply_text(f"🎨 *Today's mood:*\n\n{combo}", parse_mode="Markdown")


async def dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /dream [describe your dream]")
        return
    dream_text = " ".join(context.args)
    interpretation = random.choice(DREAM_INTERPRETATIONS)
    await update.message.reply_text(
        f"💭 *Dream:* {dream_text}\n\n*Interpretation:*\n_{interpretation}_\n\n"
        f"_(for fun only — not real dream analysis)_",
        parse_mode="Markdown",
    )


async def manifest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /manifest [what you want]")
        return
    text = " ".join(context.args)
    card = MANIFEST_TEMPLATE.format(text=text)
    await update.message.reply_text(f"🕊️ *Manifestation Card*\n\n{card}", parse_mode="Markdown")
