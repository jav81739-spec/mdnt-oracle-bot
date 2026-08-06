"""
Human-style chat: auto language/vibe mirroring + persona system +
short-term conversation memory so replies actually connect to what
was said, instead of generic filler.
"""
import os
from telegram import Update
from telegram.ext import ContextTypes

# Per-chat state (swap for a real DB in production)
chat_enabled = {}
chat_persona = {}
# {chat_id: [ {"role": "user"/"assistant", "text": str}, ... ]} — last ~10 turns
chat_history = {}

DEFAULT_PERSONA = "friendly, casual, mixes Hinglish naturally, matches the tone of whoever it's replying to"
MAX_HISTORY = 10


async def toggle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_enabled[chat_id] = not chat_enabled.get(chat_id, False)
    state = "ON ✅" if chat_enabled[chat_id] else "OFF ❌"
    await update.message.reply_text(f"Chat mode is now {state}")


async def set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    style = " ".join(context.args) if context.args else DEFAULT_PERSONA
    chat_persona[chat_id] = style
    await update.message.reply_text(f"Persona updated: {style}")


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires on every non-command message.
    Only responds if: chat mode is ON, and the bot was tagged/replied to
    (avoid replying to every single message in the group).
    """
    chat_id = update.effective_chat.id
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
