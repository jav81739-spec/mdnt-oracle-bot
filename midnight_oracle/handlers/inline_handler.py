"""Telegram inline-mode surface for lightweight Oracle prompts."""
from __future__ import annotations
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from ..generators.truth_generator import question

async def handle_inline(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """Return one formatted inline result for the requested Oracle action."""
    q=(update.inline_query.query or '').strip().casefold(); mapping={'truth':question('light'),'dare':'Send your next message using only three words. ☾','mood':'☾ Honest check-in: energy today — low, steady, or alive?','roast':'☾ Ask Oracle for a gentle roast. Dignity stays intact.','wyr':'☾ Would you rather know every truth or forget every regret?','moment':'☾ Oracle Moment: what is something good you almost missed today?','question':'☾ What has been quietly taking up space in your mind lately?'}
    text=mapping.get(q, '☾ Try: truth · dare · mood · roast · wyr · moment · question')
    result=InlineQueryResultArticle(id='oracle-'+(q or 'help'),title='☾ Oracle',description=text[:120],input_message_content=InputTextMessageContent(text))
    await update.inline_query.answer([result],cache_time=5,is_personal=False)
