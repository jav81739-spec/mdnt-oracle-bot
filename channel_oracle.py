"""
channel_oracle.py — Auto-reply to linked channel posts in discussion group
Midnight Oracle Bot

HOW IT WORKS:
- Your bot must be admin in BOTH the channel AND the linked discussion group
- When a channel post is forwarded to the discussion group (is_automatic_forward=True),
  the bot replies to it with a themed comment
- Uses Gemini to generate smart, context-aware replies based on post content
- Falls back to curated aesthetic reply pools if Gemini fails
"""

import random
import asyncio
import os
from telegram import Update, Message
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
import google.generativeai as genai

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None

# ─── Aesthetic Reply Pools ─────────────────────────────────────────────────
# Organized by content vibe — used as fallback if no Gemini

ORACLE_CHANNEL_REPLIES = {
    "generic": [
        "🌙 *the oracle has spoken* ✨",
        "👁️ the midnight hour reveals all things",
        "🖤 filed this into the shadow archives",
        "✨ the cosmos noted this. so did i.",
        "🌑 another message swallowed by the void... and kept forever",
        "🔮 fate delivers in strange packages. this was one of them",
        "💀 interesting. the Oracle raises an eyebrow from the abyss",
        "🌌 somewhere, a star rearranged itself for this moment",
        "🃏 the cards were right about this one",
        "🕯️ lighting a candle for whoever needed to hear this",
        "👁️‍🗨️ seen. processed. eternally remembered.",
        "🌙 this deserved to exist in the world. it does now.",
        "✨ the veil between worlds thinned, just for a second",
        "🖤 *midnight oracle has entered the chat*",
        "🔱 the Oracle adds this to its collection of important things",
    ],
    "photo_video": [
        "📸 the Oracle saves this to its eternal gallery 🖤",
        "🌙 visuals that feed the void. beautiful.",
        "👁️ *stares into the aesthetic*",
        "✨ frames like these make the night worth it",
        "🎞️ if moods had a color, this would be it",
        "🌑 dark and lovely in equal measure",
        "💀 this image is doing something to my soul and I'm not mad",
        "🖼️ the Oracle appreciates what the eyes cannot unsee",
        "🌌 somewhere between art and obsession. perfect.",
    ],
    "news_info": [
        "📰 the Oracle absorbs this knowledge into the void",
        "👁️ noted. processed. filed under 'things that matter'.",
        "🔮 the stars predicted this, actually",
        "🌙 information is power. power is everything.",
        "✨ the Oracle thanks the universe for this update",
        "📜 added to the ancient texts of midnight knowledge",
        "🌑 truth, even when uncomfortable, is the Oracle's favorite",
        "💡 a mind is a terrible thing to leave uninformed",
    ],
    "meme_fun": [
        "💀💀💀 THE ORACLE IS DECEASED",
        "🖤 the abyss looked into this and wheezed",
        "😭✨ why did this hit different at midnight",
        "🌙 the Oracle did NOT see that coming. 10/10",
        "💀 my sides. my sides left the chat.",
        "🃏 whoever made this is going to the underworld. we'll have fun.",
        "👁️ *processes this for 3 business days*",
        "🌑 ok this earned a star in the cosmic ratings",
        "✨ the Oracle choked on its own shadow reading this",
    ],
    "motivation": [
        "🔱 the Oracle believed in you before you believed in yourself",
        "✨ the universe whispered this specifically for someone here",
        "🌙 midnight thoughts that become morning fuel",
        "💫 saving this for a bad day. everyone should.",
        "🖤 real words. keep going.",
        "🌌 this is your sign. the Oracle confirms it.",
        "🕯️ sometimes the darkness just needed the right words",
        "💪 the cosmos nods in approval",
    ],
}

# ─── Detect content type from message ─────────────────────────────────────
def detect_content_type(message: Message) -> str:
    if message.photo or message.video or message.animation or message.video_note:
        return "photo_video"
    elif message.sticker:
        return "meme_fun"
    elif message.document:
        return "news_info"
    elif message.text:
        text_lower = (message.text or "").lower()
        # Meme/fun indicators
        if any(word in text_lower for word in ["lol", "lmao", "💀", "😭", "bruh", "bro", "bestie", "ngl", "lmfao", "kek", "😂"]):
            return "meme_fun"
        # Motivational
        elif any(word in text_lower for word in ["believe", "dream", "inspire", "motivat", "strength", "hope", "rise", "growth"]):
            return "motivation"
        # News/info
        elif any(word in text_lower for word in ["update", "news", "announce", "breaking", "report", "alert", "release"]):
            return "news_info"
    return "generic"

# ─── Generate AI comment via Gemini ───────────────────────────────────────
async def generate_ai_comment(message: Message) -> str | None:
    if not gemini_model:
        return None

    # Build context from message
    content_desc = ""
    if message.text:
        content_desc = f"Channel post text: {message.text[:500]}"
    elif message.caption:
        content_desc = f"Caption on media post: {message.caption[:300]}"
    elif message.photo:
        content_desc = "A photo was posted to the channel"
    elif message.video:
        content_desc = "A video was posted"
    elif message.sticker:
        content_desc = "A sticker was posted"
    elif message.document:
        content_desc = "A document/file was shared"
    else:
        content_desc = "A post was made to the channel"

    prompt = f"""You are Midnight Oracle — a mysterious, aesthetic, slightly dramatic Telegram group bot 
with a dark-mystic personality. You're cool, witty, a little poetic, and speak in short punchy lines.

Someone just posted to your channel. React to it with ONE short comment (1-2 lines max).
Use emojis naturally. Sound authentic, not robotic. Be engaging. 
Avoid saying 'I', avoid sounding like an AI.
Use darkness/moon/oracle/cosmic themes if natural, but don't force it.
Mix English with occasional Hindi/Hinglish vibes if the content feels Indian.

Post context: {content_desc}

Reply with ONLY the comment text, nothing else. Keep it under 100 characters."""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_model.generate_content(prompt)
        )
        comment = response.text.strip()
        if comment and len(comment) < 300:
            return comment
    except Exception as e:
        print(f"[ChannelOracle] Gemini error: {e}")

    return None

# ─── Main channel post handler ─────────────────────────────────────────────
async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a channel post is auto-forwarded to the linked discussion group.
    The bot replies to it in the group's comment thread.
    """
    message = update.message

    # Only handle auto-forwards from linked channel
    if not message or not message.is_automatic_forward:
        return

    # Small delay so it feels human, not instant-bot
    await asyncio.sleep(random.uniform(2.5, 7.0))

    # Try Gemini first
    comment = await generate_ai_comment(message)

    # Fallback to curated pool
    if not comment:
        content_type = detect_content_type(message)
        pool = ORACLE_CHANNEL_REPLIES.get(content_type, ORACLE_CHANNEL_REPLIES["generic"])
        comment = random.choice(pool)

    try:
        await message.reply_text(
            comment,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        # Try without markdown if parse error
        try:
            clean = comment.replace("*", "").replace("_", "").replace("`", "")
            await message.reply_text(clean)
        except Exception as e2:
            print(f"[ChannelOracle] Reply failed: {e2}")

# ─── Handler registration helper ───────────────────────────────────────────
def get_channel_oracle_handler():
    """
    Returns the MessageHandler to register in your main bot.
    Add this in your main.py:
    
        from channel_oracle import get_channel_oracle_handler
        app.add_handler(get_channel_oracle_handler())
    
    Your bot needs to be:
    1. Admin in the linked Telegram channel
    2. Admin (or at least member) in the linked discussion group
    """
    return MessageHandler(
        filters.IS_AUTOMATIC_FORWARD,
        handle_channel_post_in_group
    )
