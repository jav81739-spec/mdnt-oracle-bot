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
COOLDOWN_SECONDS = 3  # minimum gap between AI replies per chat — protects free quota

STORAGE_KEY = "chat_settings"

_last_reply_time = {}  # {"<chat_id>": float timestamp} — not persisted, resets on restart, that's fine


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
    # Trigger word: saying "midnight" anywhere in a message wakes the bot up,
    # same as tagging it — feels more natural, like calling someone's name.
    was_keyword_triggered = "midnight" in (message.text or "").lower()

    if not (was_mentioned or was_replied_to or was_keyword_triggered):
        return

    import time
    now = time.time()
    if now - _last_reply_time.get(chat_id, 0) < COOLDOWN_SECONDS:
        return  # too soon since last reply — stay quiet rather than spam-triggering the API
    _last_reply_time[chat_id] = now

    persona = chat_persona.get(chat_id, DEFAULT_PERSONA)

    # Track history per chat so replies stay connected to the conversation
    chat_history.setdefault(chat_id, [])
    chat_history[chat_id].append({"role": "user", "text": message.text})
    chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]

    try:
        reply_text = await generate_reply(message.text, persona, chat_history[chat_id])
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Gemini API call failed: {e}")

        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "rate" in error_str:
            # Free tier hit its request limit — sounds like the bot is
            # just "thinking" or "resting," not broken, to the group.
            await message.reply_text("🌙 give me a sec, catching my breath... try again in a minute 😌")
        else:
            # Any other failure — stay vague and in-character rather than
            # dumping a technical error in front of the group. Full details
            # are already in the Render logs above for us to debug together.
            await message.reply_text("🌙 my thoughts got a little tangled just now — try that again?")
        return

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
        model_name="gemini-3.5-flash",  # gemini-2.0-flash was shut down June 1 2026 — this was the actual bug
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
    "CAACAgUAAxkBAAEGBzJqdp9ai3sYNonxPitgXwW1HsGYLQACigEAAqMYnj7IByAbmW8_0z0E",
    "CAACAgUAAxkBAAEGBzBqdp8mL5Juj0jyC3nh7q2mdBwJbAACyRMAAlJekFeBRat3I0udiz0E",
    "CAACAgUAAxkBAAEGBy5qdp8Uv6Pi3-VK9BJ7nn8_08Ju5wACsQQAAqQhMVYQIkv-OAABHc49BA",
    "CAACAgUAAxkBAAEGByxqdp7ystKCl2Rj7YKklllelMrR2gACqRUAAkggCFejMbHj9ySCNj0E",
    "CAACAgUAAxkBAAEGByZqdp6sg55QIGUcBVbW5ZvbvR1B8QACFhEAAlYTiVduxmgSyR8nUT0E",
    "CAACAgUAAxkBAAEGBxxqdp587c9-Vw1hftneSbQ9pWWtXQAC5BgAAremsVRaWlNEWRIuZz0E",
    "CAACAgUAAxkBAAEGBxpqdp5twHyvyAABbNEdbXdkTXCb7eAAAukaAAK32rhVVsDSda6ab2w9BA",
    "CAACAgUAAxkBAAEGBzRqdp_FeJQQ3EJfKq_Y7fZ-5l9lngAC5wEAAq4xRgWFtzPKdb1ZuD0E",
    "CAACAgUAAxkBAAEGBzZqdp_rySrqxo6FHWJ7J7VCq9HesAAC_xAAAn9jEVbXO-B4ukFDLz0E",
    "CAACAgUAAxkBAAEGBzhqdqAQk68E9J2t0sf1bwMizD3_ogACqgMAAnC-SFblo1QW5PoU0D0E",
    "CAACAgUAAxkBAAEGDn9qeGY4_JoN1L6EAu56kQPx5H8hhgACCgQAAsIkiFcGn8ZlVTJpDz0E",
]

# Tracks which stickers were recently used per chat, so the same one
# doesn't fire back-to-back — makes the full set of 11 actually feel used.
_recent_stickers = {}  # {"<chat_id>": [sticker_id, ...]} — last few used


def _pick_sticker(chat_id: str) -> str:
    recent = _recent_stickers.get(chat_id, [])
    # Avoid repeating any of the last 4 used, if enough variety exists
    available = [s for s in SAMPLE_STICKERS if s not in recent] or SAMPLE_STICKERS
    choice = _random.choice(available)
    recent.append(choice)
    _recent_stickers[chat_id] = recent[-4:]  # keep only last 4
    return choice

GIF_SEARCH_TERMS = ["funny reaction", "excited", "lol", "confused", "celebration", "facepalm"]

REACTION_EMOJIS = ["👍", "🔥", "🎉", "👀", "😁"]

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
    sticker_id = _pick_sticker(str(update.effective_chat.id))
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


async def get_gif_url(term: str) -> str | None:
    """
    Fetches a real GIF url from GIPHY for the given search term.
    Returns None if GIPHY_API_KEY isn't set or nothing is found —
    callers should fall back to plain text in that case.
    """
    api_key = os.getenv("GIPHY_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.giphy.com/v1/gifs/search",
                params={"q": term, "api_key": api_key, "limit": 15, "rating": "pg-13"},
            )
        data = resp.json()
        results = data.get("data", [])
        if not results:
            return None
        chosen = _random.choice(results)
        return chosen["images"]["original"]["url"]
    except Exception:
        return None


async def send_text_with_gif(bot, chat_id: int, text: str, term: str, parse_mode: str = "Markdown", reply_to_message_id: int = None):
    """
    Sends text and a matching GIF as ONE combined message (GIF with the
    text as its caption), instead of two separate messages. Falls back
    to plain text only if no GIF is available (no API key or no results),
    so this never breaks a command even without GIF support configured.
    """
    gif_url = await get_gif_url(term)
    if gif_url:
        await bot.send_animation(
            chat_id, gif_url, caption=text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id
        )
    else:
        await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id)


async def send_mood_gif(bot, chat_id: int, term: str):
    """Kept for backward compatibility — sends a GIF with no caption."""
    gif_url = await get_gif_url(term)
    if gif_url:
        await bot.send_animation(chat_id, gif_url)


async def gif_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when someone sends a GIF/animation AS A REPLY to the bot's own
    message. Fetches a real random GIF from GIPHY and replies with it,
    tagging the sender (GIFs also can't carry text captions with mentions
    reliably across all clients, so the tag goes in a short text message
    alongside it, same pattern as sticker_reply).
    """
    chat_id = str(update.effective_chat.id)
    if not chat_enabled.get(chat_id, False):
        return

    was_replied_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    if not was_replied_to_bot:
        return

    api_key = os.getenv("GIPHY_API_KEY")
    if not api_key:
        return  # GIF feature not configured yet — stay silent, don't spam an error

    from handlers.mentions import mention
    sender = update.effective_user
    term = _random.choice(GIF_SEARCH_TERMS)

    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.giphy.com/v1/gifs/search",
            params={"q": term, "api_key": api_key, "limit": 20, "rating": "pg-13"},
        )
    data = resp.json()
    results = data.get("data", [])
    if not results:
        return

    chosen = _random.choice(results)
    gif_url = chosen["images"]["original"]["url"]

    await context.bot.send_animation(
        update.effective_chat.id, gif_url, reply_to_message_id=update.message.message_id
    )


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
    except Exception as e:
        import logging
        logging.getLogger(__name__).info(
            f"Reaction failed (likely group has reactions restricted/disabled): {e}"
        )


async def sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when someone sends a sticker AS A REPLY to the bot's own
    message specifically — not just any sticker sent anywhere in the
    chat. This keeps it intentional (someone replying to the bot with
    a sticker) instead of random/spammy.

    Tags the sender by name (Telegram stickers can't carry captions, so
    the mention goes in a short text message alongside the sticker,
    which is also reply-threaded directly to their message).
    """
    chat_id = str(update.effective_chat.id)
    if not chat_enabled.get(chat_id, False):
        return

    was_replied_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    if not was_replied_to_bot:
        return

    if not SAMPLE_STICKERS or SAMPLE_STICKERS[0] == "CAACAgIAAxkBAAEBdummy1":
        return  # no real stickers configured yet — stay silent, don't spam an error

    sticker_id = _pick_sticker(chat_id)
    await context.bot.send_sticker(
        update.effective_chat.id, sticker_id, reply_to_message_id=update.message.message_id
    )
