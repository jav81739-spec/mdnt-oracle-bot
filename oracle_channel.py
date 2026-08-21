"""
channel_oracle.py — Auto-reply to channel posts IN THE DISCUSSION GROUP
Midnight Oracle Bot

HOW IT WORKS:
When you post to your channel, Telegram auto-forwards it to the linked
discussion group with is_automatic_forward=True. Bot replies to THAT
message in the group — appears as a comment visible to all members. ✅

SETUP:
  1. Channel Settings → Discussion → link your group
  2. Bot must be ADMIN in the discussion GROUP (Send Messages permission)
  3. Bot does NOT need to be in the channel
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import asyncio
import os
import logging

from telegram import Update, Message
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

_gemini_model = None

def _get_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
            _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"[ChannelOracle] Gemini not available: {e}")
    return _gemini_model

ORACLE_REPLIES = {
    "photo": [
        "📸 oracle saves this to the eternal gallery 🖤",
        "🌙 visuals that feed the void. beautiful.",
        "👁️ *stares into the aesthetic for 3 business days*",
        "✨ frames like these make the night worth it",
        "🌑 dark and lovely in equal measure",
        "💀 this image is doing something to the oracle's soul and we're not mad",
    ],
    "video": [
        "🎬 the oracle has watched this 7 times. not stopping.",
        "🌙 moving pictures that move something deeper 🖤",
        "✨ this deserved to exist. it does now.",
        "👁️ the oracle pressed replay. and again.",
        "💀 okay but WHY did this hit so different",
    ],
    "meme": [
        "💀💀💀 THE ORACLE IS DECEASED",
        "🖤 the abyss looked into this and wheezed",
        "😭✨ why does this hit different at this hour",
        "🌙 the oracle did NOT see that coming. 10/10",
        "👁️ *processes this for 3 business days*",
        "✨ the oracle choked on its own shadow reading this",
        "💀 my sides have LEFT the chat",
        "🌑 ok whoever made this is unhinged. we love them.",
    ],
    "motivation": [
        "🔱 the oracle believed in you before you believed in yourself",
        "✨ the universe whispered this for someone here specifically",
        "🌙 midnight thoughts that become morning fuel",
        "🖤 real words. keep going.",
        "🌌 this is your sign. the oracle confirms it.",
        "🕯️ sometimes the dark just needed the right words",
    ],
    "news": [
        "📰 the oracle absorbs this into the cosmic archives",
        "👁️ noted. processed. filed under things that matter.",
        "🌙 information is power. power is everything.",
        "📜 added to the ancient texts of midnight knowledge",
    ],
    "generic": [
        "🌙 *the oracle has spoken* ✨",
        "👁️ the midnight hour reveals all things",
        "🖤 filed this into the shadow archives",
        "✨ the cosmos noted this. so did the oracle.",
        "🌑 another message kept by the void forever",
        "🔮 fate delivers in strange packages. this was one of them.",
        "💀 interesting. the oracle raises an eyebrow from the abyss",
        "🌌 somewhere, a star rearranged itself for this moment",
        "🃏 the cards were right about this one",
        "🕯️ lighting a candle for whoever needed to see this",
        "👁️‍🗨️ seen. processed. eternally remembered.",
        "🌙 this deserved to exist in the world. it does now.",
        "🖤 *midnight oracle has entered the comments*",
        "🔱 adding this to the collection of important things",
        "✨ cosmic acknowledgment received 🌙",
        "👁️ the oracle was here. always watching. always vibing.",
        "💫 the night delivers, and the oracle receives",
        "🌑 the oracle sees all. judges none. vibes with all.",
    ],
}

def _detect_type(message: Message) -> str:
    if message.video or message.video_note:
        return "video"
    if message.photo or message.animation:
        cap = (message.caption or "").lower()
        if any(w in cap for w in ["💀", "😭", "lol", "lmao", "bruh"]):
            return "meme"
        return "photo"
    if message.sticker:
        return "meme"
    if message.text:
        t = message.text.lower()
        if any(w in t for w in ["💀", "😭", "lol", "lmao", "bruh", "kek", "😂", "🤣"]):
            return "meme"
        if any(w in t for w in ["inspire", "motivat", "believe", "dream", "hope", "keep going"]):
            return "motivation"
        if any(w in t for w in ["news", "update", "breaking", "announce", "alert"]):
            return "news"
    return "generic"

async def _ai_comment(message: Message) -> str | None:
    model = _get_gemini()
    if not model:
        return None

    if message.text:
        content = f"Channel post text: {message.text[:400]}"
    elif message.caption:
        content = f"Media caption: {message.caption[:300]}"
    elif message.photo:
        content = "A photo was posted"
    elif message.video:
        content = "A video was posted"
    elif message.animation:
        content = "A GIF was posted"
    elif message.sticker:
        content = "A sticker was posted"
    elif message.poll:
        content = f"A poll: {message.poll.question}"
    else:
        content = "A post was made to the channel"

    prompt = f"""You are Midnight Oracle — a mysterious, warm, poetic Telegram group bot.
You're leaving a comment on a channel post in the discussion section.

YOUR STYLE:
- Short, punchy, 1-2 lines MAX
- Mysterious + warm + occasionally funny
- 1-2 emojis naturally (moon, star, void, eye themes)
- Sound like a cool friend, not a robot
- Never say "I am an AI"
- Occasionally Hinglish if the post feels Indian

Post context: {content}

Write ONLY the comment. Under 80 characters preferred. Nothing else."""

    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, lambda: model.generate_content(prompt)
        )
        text = (resp.text or "").strip().replace("```", "")
        if text and len(text) < 280:
            return text
    except Exception as e:
        logger.warning(f"[ChannelOracle] Gemini error: {e}")
    return None

async def handle_channel_post_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a channel post is auto-forwarded to the linked discussion group.
    Bot replies to it in the GROUP — shows up as a comment on the channel post.
    """
    message = update.message
    if not message or not message.is_automatic_forward:
        return

    await asyncio.sleep(random.uniform(2.0, 8.0))

    comment = await _ai_comment(message)

    if not comment:
        ctype = _detect_type(message)
        pool = ORACLE_REPLIES.get(ctype, ORACLE_REPLIES["generic"])
        comment = random.choice(pool)

    try:
        await message.reply_text(comment, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"[ChannelOracle] Commented in chat {message.chat.id}")
    except Exception:
        try:
            plain = comment.replace("*", "").replace("_", "").replace("`", "")
            await message.reply_text(plain)
        except Exception as e2:
            logger.error(f"[ChannelOracle] Reply failed: {e2}")

def get_channel_oracle_handler():
    return MessageHandler(
        filters.IS_AUTOMATIC_FORWARD & filters.ChatType.GROUPS,
        handle_channel_post_in_group,
    )
