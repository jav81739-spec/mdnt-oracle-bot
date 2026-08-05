"""
Human-style chat: auto language/vibe mirroring + persona system.
Plug in your AI API call inside `generate_reply()`.
"""
import os
import random
from telegram import Update
from telegram.ext import ContextTypes

# Per-chat state (swap for a real DB in production)
chat_enabled = {}
chat_persona = {}

DEFAULT_PERSONA = "friendly, casual, mixes Hinglish naturally, matches the tone of whoever it's replying to"


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
    reply_text = await generate_reply(message.text, persona)
    await message.reply_text(reply_text)


async def generate_reply(user_text: str, persona: str) -> str:
    """
    Wire this up to an AI API (Anthropic, OpenAI, etc).
    The prompt below is what makes language/vibe mirroring work:
    it explicitly tells the model to match language AND tone.
    """
    system_prompt = (
        f"You are a Telegram group chat member. Personality: {persona}. "
        "CRITICAL: Reply in the SAME language/script the user used "
        "(English, Hindi, Hinglish, or Romanized Hindi) — mirror it exactly. "
        "Also match their tone/energy: casual stays casual, sarcastic gets "
        "sarcastic back, serious gets a straight answer. Keep replies short, "
        "like a real chat message, not an essay."
    )

    # ---- Example using Anthropic API (uncomment and configure) ----
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=200,
    #     system=system_prompt,
    #     messages=[{"role": "user", "content": user_text}],
    # )
    # return response.content[0].text

    # Placeholder until API is wired in:
    return random.choice([
        "Haan bhai, sach mein? 😄",
        "That's actually a good point ngl",
        "Arre wah, batao aur",
    ])
