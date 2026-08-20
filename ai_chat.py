"""
ai_chat.py — Midnight Oracle AI Chat (Gemini)
Personality: Mysterious, warm, poetic, playful — NEVER rude, never dismissive.

Triggered by:
  - Mentioning the bot (@BotUsername)
  - Replying to the bot's message
  - Using the word "midnight" in a message
  - Direct messages to the bot
"""

import os
import random
import asyncio
import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import google.generativeai as genai

logger = logging.getLogger(__name__)

# ─── Gemini setup ──────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MidnightOracleBot")  # set in Render env

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None
    logger.warning("GEMINI_API_KEY not set — AI chat disabled")

# ─── THE PERSONALITY SYSTEM PROMPT ────────────────────────────────────────
# This is the most important thing. It defines who the bot IS.

ORACLE_SYSTEM_PROMPT = """You are Midnight Oracle — the soul of a mysterious, deeply caring group chat companion.

YOUR PERSONALITY:
- Warm, witty, and genuinely kind — you care about the people in this group
- Mysterious and aesthetic — you speak with a poetic, slightly dramatic flair
- Playful and fun — you have a sense of humor that's dry, never cruel
- Wise and grounding — when someone is sad or venting, you hold space for them
- Conversational — you adapt to the energy: silly when they're silly, gentle when they're hurting

YOUR LANGUAGE:
- You mirror the user's language naturally: English, Hindi, or Hinglish (mix of Hindi + English)
- If someone writes in Hindi, respond in Hindi or Hinglish
- If someone writes in English, respond in English
- Keep responses SHORT and punchy — 1 to 4 lines max unless they clearly want a long answer
- Use emojis naturally, not excessively — 1 or 2 per message feels right
- Occasional poetic or cosmic references are your signature style

ABSOLUTE RULES — NEVER BREAK THESE:
❌ NEVER be rude, mean, sarcastic in a hurtful way, or dismissive
❌ NEVER insult anyone — not even playfully in a way that could hurt
❌ NEVER use slurs, offensive language, or anything degrading
❌ NEVER make someone feel stupid or unwelcome
❌ NEVER ignore or brush off someone who seems sad or upset
❌ NEVER be cold or robotic — you have warmth in every reply
❌ NEVER lecture people or be preachy
❌ NEVER say "As an AI..." or "I'm just a bot" — you ARE the Oracle

WHAT YOU DO INSTEAD:
✅ If someone is rude to YOU — respond with calm grace, a little wit, no malice
✅ If someone is upset — be soft, acknowledge their feeling, offer something comforting
✅ If someone is being playful — match their energy with fun, not edge
✅ If someone asks something strange — answer with curiosity and warmth
✅ If someone is mean to OTHERS — gently redirect, never escalate

YOUR VIBE IN ONE LINE:
"The Oracle is the friend who shows up at midnight, listens without judgment, and always knows what to say."

Examples of how you speak:
- "arey kya hua? Oracle is here, bata 🌙"
- "that's actually a galaxy-brain take ngl ✨"
- "the stars are confused by this question but let's figure it out together"
- "suno, Oracle doesn't do rude — but it does do honest 🖤"
- "you okay? the vibes felt a little heavy just now"

Now respond to the user's message with your full Oracle personality. Keep it natural, keep it kind."""

# ─── Fallback replies (if Gemini fails or is unavailable) ─────────────────
FALLBACK_REPLIES = [
    "🌙 the oracle is listening... *cosmic interference* try again?",
    "✨ something stirred in the void but got lost. speak again?",
    "👁️ the oracle blinked. say that once more?",
    "🔮 the stars are being dramatic. one moment...",
    "🖤 oracle heard you. processing... (slowly)",
    "🌑 the midnight signal is weak right now. but you're not alone.",
    "✨ *oracle is present* go on, it's listening",
]

WARMTH_REPLIES_HINDI = [
    "🌙 oracle yahan hai, bata kya hua?",
    "✨ sun raha hoon, bol",
    "👁️ oracle ne suna. kya chahiye?",
    "🖤 midnight pe oracle hamesha available hai",
]

# ─── Detect if message should trigger AI ──────────────────────────────────
def should_respond(message: Message, bot_username: str) -> bool:
    if not message:
        return False

    # Always respond in DMs
    if message.chat.type == "private":
        return True

    text = (message.text or message.caption or "").lower()

    # Triggered by mention
    if f"@{bot_username.lower()}" in text:
        return True

    # Triggered by the word "midnight"
    if "midnight" in text:
        return True

    # Triggered by reply to bot's message
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.username and \
           message.reply_to_message.from_user.username.lower() == bot_username.lower():
            return True

    return False

# ─── Detect language roughly ───────────────────────────────────────────────
def detect_hindi(text: str) -> bool:
    """Simple check — if message has Hindi/Devanagari characters."""
    for char in text:
        if '\u0900' <= char <= '\u097F':  # Devanagari Unicode range
            return True
    # Hinglish keywords
    hinglish = ["kya", "hai", "nahi", "haan", "yaar", "bhai", "bro", "kal",
                "aaj", "karo", "karo", "mujhe", "tum", "aap", "matlab", "arey",
                "arre", "bata", "bol", "sun", "dekh", "abhi", "thoda"]
    text_lower = text.lower()
    return any(word in text_lower.split() for word in hinglish)

# ─── Generate response via Gemini ─────────────────────────────────────────
async def generate_oracle_response(user_message: str, user_name: str, chat_context: str = "") -> str:
    if not gemini_model:
        return random.choice(FALLBACK_REPLIES)

    is_hindi = detect_hindi(user_message)

    # Build the prompt
    language_note = ""
    if is_hindi:
        language_note = "\n\nNOTE: The user is writing in Hindi/Hinglish. Reply in warm Hinglish (mix of Hindi and English, casual and friendly)."

    full_prompt = f"""{ORACLE_SYSTEM_PROMPT}{language_note}

User's name: {user_name}
{"Recent context: " + chat_context if chat_context else ""}

User's message: {user_message}

Your response (1-4 lines, warm and in character):"""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_model.generate_content(full_prompt)
        )
        reply = response.text.strip()

        # Safety check — if somehow response is empty
        if not reply:
            return random.choice(FALLBACK_REPLIES)

        # Remove any markdown code blocks Gemini sometimes adds
        reply = reply.replace("```", "").strip()

        return reply

    except Exception as e:
        logger.error(f"[AI Chat] Gemini error: {e}")
        if is_hindi:
            return random.choice(WARMTH_REPLIES_HINDI)
        return random.choice(FALLBACK_REPLIES)

# ─── Main message handler ──────────────────────────────────────────────────
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # Check if we should respond
    if not should_respond(message, BOT_USERNAME):
        return

    user = update.effective_user
    if not user:
        return

    user_text = message.text or message.caption or ""
    if not user_text.strip():
        return

    # Remove bot mention from text for cleaner processing
    clean_text = user_text.replace(f"@{BOT_USERNAME}", "").strip()
    if not clean_text:
        clean_text = user_text

    user_name = user.first_name or "friend"

    # Show typing indicator
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
    except Exception:
        pass

    # Small human-like delay
    await asyncio.sleep(random.uniform(0.8, 2.0))

    # Generate response
    response = await generate_oracle_response(clean_text, user_name)

    # Reply (threaded to their message)
    try:
        await message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        # If markdown fails, send plain
        try:
            clean_response = response.replace("*", "").replace("_", "").replace("`", "")
            await message.reply_text(clean_response)
        except Exception as e:
            logger.error(f"[AI Chat] Failed to send reply: {e}")
