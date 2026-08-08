"""
Human-style chat: auto language/vibe mirroring + persona system +
short-term conversation memory so replies actually connect to what
was said, instead of generic filler.

PERSISTED: chat_enabled and chat_persona are now saved via
handlers/storage.py (Upstash Redis), so a Render restart no longer
silently turns your chat mode back OFF without you knowing — that
was the most common reason the bot appeared to "stop talking."
"""
import os
from telegram import Update
from telegram.ext import ContextTypes
from handlers import storage

# In-memory cache, mirrored to Redis on every change.
chat_enabled = {}  # {"<chat_id>": bool}
chat_persona = {}  # {"<chat_id>": str}
# Short-term conversation memory — intentionally NOT persisted, since it's
# only meant to cover the current conversation, not survive restarts.
chat_history = {}

DEFAULT_PERSONA = "friendly, casual, mixes Hinglish naturally, matches the tone of whoever it's replying to"
MAX_HISTORY = 10

STORAGE_KEY = "chat_settings"


async def load_from_storage():
    """Call once at bot startup to restore chat mode + persona settings."""
    global chat_enabled, chat_persona
    saved = await storage.load(STORAGE_KEY, {"enabled": {}, "persona": {}})
    chat_enabled = saved.get("enabled", {})
    chat_persona = saved.get("persona", {})


async def _persist():
    await storage.save(STORAGE_KEY, {"enabled": chat_enabled, "persona": chat_persona})


async def toggle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    chat_enabled[chat_id] = not chat_enabled.get(chat_id, False)
    await _persist()
    state = "ON ✅" if chat_enabled[chat_id] else "OFF ❌"
    await update.message.reply_text(
        f"Chat mode is now {state}\n"
        f"_(this now stays saved even if the bot restarts)_",
        parse_mode="Markdown",
    )


async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    style = " ".join(context.args) if context.args else DEFAULT_PERSONA
    chat_persona[chat_id] = style
    await _persist()
    await update.message.reply_text(f"Persona updated: {style}")


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires on every non-command message.
    Only responds if: chat mode is ON, and the bot was tagged/replied to
    (avoid replying to every single message in the group).
    """
    chat_id = str(update.effective_chat.id)
    if not chat_enabled.get(chat_id, False):
        return

    message = update.message
    bot_username = context.bot.username
    was_mentioned = bot_username and f"@{bot_username}" in (message.text or "")
    was_replied_to = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == context.bot.id
    )

    if not (was_mentioned or was_replied_to):
        return

    persona = chat_persona.get(chat_id, DEFAULT_PERSONA)

    # Track history per chat so replies stay connected to the conversation
    chat_history.setdefault(chat_id, [])
    chat_history[chat_id].append({"role": "user", "text": message.text})
    chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]

    reply_text = await generate_reply(message.text, persona, chat_history[chat_id])

    if reply_text is None:
        # No API key configured — say so honestly instead of sending a
        # disconnected placeholder reply.
        await message.reply_text(
            "🔌 AI chat isn't wired up yet — add a free GEMINI_API_KEY to "
            "your .env (see README) and I'll actually reply properly."
        )
        return

    chat_history[chat_id].append({"role": "assistant", "text": reply_text})
    chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]
    await message.reply_text(reply_text)


async def generate_reply(user_text: str, persona: str, history: list) -> str | None:
    """
    Calls Google Gemini (free tier). Returns None if no API key is set,
    so the caller can be honest with the user instead of faking a reply.

    The system prompt + conversation history together are what make
    replies actually connect to what's being said, instead of generic
    filler lines with no relation to the message.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    system_prompt = (
        f"You are a real member of a Telegram group chat. Personality: {persona}. "
        "RULES:\n"
        "1. Reply in the SAME language/script the user just used — English, "
        "Hindi (Devanagari), or Hinglish (Romanized mix) — mirror it exactly. "
        "If they mix languages mid-sentence, you can too.\n"
        "2. Match their tone/energy: casual stays casual, sarcastic gets "
        "sarcastic back, a real question gets a real, directly relevant answer.\n"
        "3. Your reply MUST directly connect to what they just said — reference "
        "the actual content of their message. Never send a generic, unrelated, "
        "or filler response that could apply to any message.\n"
        "4. Keep it short, like a real chat message — 1-2 sentences, not an essay.\n"
        "5. Use the recent conversation history for context, but respond "
        "specifically to the newest message."
    )

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )

    # Feed recent turns so the model has real context, not just the last line
    convo_lines = []
    for turn in history[:-1]:  # exclude the newest message, sent separately below
        speaker = "Them" if turn["role"] == "user" else "You"
        convo_lines.append(f"{speaker}: {turn['text']}")
    context_block = "\n".join(convo_lines)

    prompt = (
        f"Recent conversation:\n{context_block}\n\n"
        f"Their newest message: {user_text}\n\n"
        "Reply directly to their newest message, using the context above only "
        "if it's relevant."
    ) if context_block else user_text

    response = model.generate_content(prompt)
    return response.text.strip()


# ---- Stickers, GIFs, and random reactions ----
# Public Telegram sticker set names (anyone can use these via file_id lookup,
# but simplest reliable approach: use well-known public sticker set short-names)
STICKER_SETS = [
    "AnimatedEmojies",  # generic animated pack, publicly usable
]

# A small set of direct sticker file_ids from Telegram's default packs.
# These are stable, public, and don't require your bot to own the pack.
SAMPLE_STICKERS = [
    "CAACAgIAAxkBAAEBdummy1",  # placeholder — replace with real file_ids, see note below
]

GIF_SEARCH_TERMS = ["funny reaction", "excited", "lol", "confused", "celebration", "facepalm"]

REACTION_EMOJIS = ["👍", "😂", "🔥", "❤️", "😢", "🎉", "🤔", "👀"]

import random as _random


async def get_sticker_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /getstickerid — reply to any sticker with this command, and the bot
    tells you its file_id. Collect a few of these, send them back to me,
    and I'll wire them into the real /sticker command.
    """
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
        await update.message.reply_text("Reply to a sticker with /getstickerid to grab its ID")
        return
    sticker = update.message.reply_to_message.sticker
    await update.message.reply_text(f"📎 Sticker file_id:\n`{sticker.file_id}`", parse_mode="Markdown")


async def send_random_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /sticker — sends a random sticker.
    NOTE: Telegram requires real sticker file_ids or a real pack name to
    send stickers — there's no universal "random sticker" API. The
    honest setup: use /getstickerid on a few stickers you like, send me
    the IDs, and I'll wire them into SAMPLE_STICKERS below.
    """
    if not SAMPLE_STICKERS or SAMPLE_STICKERS[0] == "CAACAgIAAxkBAAEBdummy1":
        await update.message.reply_text(
            "🎨 Sticker feature needs real sticker IDs first — Telegram doesn't "
            "have a generic 'random sticker' API. Use /getstickerid (reply to "
            "a sticker) to grab some IDs, send them to me, and I'll wire them in."
        )
        return
    sticker_id = _random.choice(SAMPLE_STICKERS)
    await context.bot.send_sticker(update.effective_chat.id, sticker_id)


async def send_random_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /gif [search term] — fetches a real random GIF from GIPHY's free API.
    Needs GIPHY_API_KEY set in your environment (see README — free signup
    at developers.giphy.com, no credit card required). Without it, tells
    you clearly instead of failing silently.
    """
    api_key = os.getenv("GIPHY_API_KEY")
    if not api_key:
        await update.message.reply_text(
            "🎬 GIFs need a free GIPHY_API_KEY — sign up at developers.giphy.com "
            "(no card needed), see README for the 2-minute setup."
        )
        return

    term = " ".join(context.args) if context.args else _random.choice(GIF_SEARCH_TERMS)

    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.giphy.com/v1/gifs/search",
            params={"q": term, "api_key": api_key, "limit": 20, "rating": "pg-13"},
        )
    data = resp.json()
    results = data.get("data", [])
    if not results:
        await update.message.reply_text(f"No GIFs found for '{term}' — try a different term.")
        return

    chosen = _random.choice(results)
    gif_url = chosen["images"]["original"]["url"]
    await context.bot.send_animation(update.effective_chat.id, gif_url)


async def maybe_react_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Call on every message: small random chance the bot reacts with an
    emoji, like a real member would — without replying every time.
    """
    if not update.message:
        return
    chat_id = str(update.effective_chat.id)
    if not chat_enabled.get(chat_id, False):
        return
    if _random.random() > 0.08:  # ~8% chance per message, keeps it natural not spammy
        return
    try:
        await context.bot.set_message_reaction(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            reaction=_random.choice(REACTION_EMOJIS),
        )
    except Exception:
        pass  # reactions can fail silently (permissions, old message, etc.) — not critical
