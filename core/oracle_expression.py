"""Canonical presentation layer for Midnight Oracle user-facing moments.

Command engines remain authoritative for facts, state, permissions and game
mechanics. This module changes presentation only, so the same command can feel
like Midnight Oracle instead of a fixed notification template.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict, deque
from typing import Iterable

from core.ai import AIUnavailable, service

_SEM = asyncio.Semaphore(3)
_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_HISTORY: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=18))
_MEDIA_BRIDGE_INSTALLED = False

_BANNED = (
    "the algorithm", "algorithm has", "internal score", "hidden score",
    "selected randomly", "randomly selected", "member data", "internal data",
    "i scanned", "i scan", "silent scan", "filed in the archives",
    "permanent record", "oracle-certified", "no further explanation",
    "inside the oracle's records", "records patterns", "does not explain",
    "conversational gravity", "quiet pull", "signal ·", "signal:",
    "test message", "testing message", "test output", "testing output",
    "debug message", "debug output", "placeholder message", "placeholder output",
)

MECHANICAL_COMMANDS = {
    "id", "info", "remind", "groupinfo", "afk", "report", "stats", "topactive",
    "msgcount", "balance", "daily", "richest", "coinboard", "rob", "withdraw",
    "deposit", "wallet", "buy", "inventory", "chests", "shop", "settings",
    "fastmath", "wordbomb", "riddleanswer", "hangmanguess", "wordleguess", "ttt",
    "chainword", "unscramble", "survive", "revive", "deathstatus", "roulette", "kill",
    "vote", "startround", "endgame", "deathgame", "mute", "unmute", "ban", "kick",
    "warn", "warnings", "clearwarns", "pin", "unpin", "purge", "rules", "setrules",
    "lock", "unlock", "setwelcome", "setgoodbye", "invite", "setcommands", "reload",
    "shutdown", "restart", "admin", "broadcast", "announce", "ownerstatus", "ownerstats",
    "midnightmap", "chat", "persona", "quiet", "wake", "forget", "memory", "mymemory",
    "help", "start", "predict", "predictions", "tod", "wyr", "nhie", "scramble",
    "poll", "settrigger", "triggerinfo",
}

def _clean(text: str) -> str:
    value = re.sub(r"```(?:\w+)?|```", "", text or "")
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value[:3800]

def _fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.casefold()).encode()).hexdigest()

def _protected_tokens(text: str) -> list[str]:
    patterns = (r"@[A-Za-z0-9_]{2,}", r"\b\d{1,3}(?:[.,:]\d{1,3})*(?:%|/100)?\b", r"\b\d{1,2}:\d{2}(?::\d{2})?\b", r"https?://\S+", r"tg://\S+")
    found: list[str] = []
    for pattern in patterns: found.extend(re.findall(pattern, text or ""))
    return list(dict.fromkeys(found))

def _safe(text: str, raw: str) -> bool:
    if not text or len(text) > 3800: return False
    low = text.casefold()
    if any(item in low for item in _BANNED): return False
    return all(token in text for token in _protected_tokens(raw))

def _fallback(raw: str, command: str) -> str:
    return raw.strip()

def _prompt(raw: str, command: str, context: str, recent: Iterable[str]) -> str:
    recent_text = "\n".join(f"- {x[:500]}" for x in list(recent)[-6:]) or "- none"
    return f"""You are the voice behind Midnight Oracle.

The command engine has ALREADY completed the action. The supplied message is truthful command output. Rewrite ONLY the human-facing prose. Never change, add, infer, or remove meaning: preserve names, usernames, numbers, percentages, times, URLs, IDs, choices, results, winners, balances, permissions, countdowns, and every other factual detail exactly.

MIDNIGHT ORACLE'S VOICE:
Think of a sharp, observant person awake late at night who happens to speak through a bot. Warm when warmth is earned, sly when the moment is playful, quiet when the moment is serious, occasionally dry, occasionally mischievous. The voice has taste but does not perform a persona. It notices the human moment without narrating its own machinery. It can sound like natural Hinglish when the source/context is Hinglish; otherwise match the user's language. It does NOT turn every line into poetry, mysticism, a horoscope, a dashboard, or a "deep" quote.

Make this feel written NOW for THIS moment. Vary sentence length, openings, rhythm, punctuation, emoji use, and degree of warmth. Sometimes be very simple. Sometimes use a small unexpected phrase. Sometimes leave the line clean. Do not manufacture a punchline or a philosophical lesson. Do not force an emoji. Do not force a title, divider, signature, percentage, or Oracle label. Do not repeat recent wording or fall into a recognizable output pattern.

This is command /{command}. Keep the command's identity and purpose obvious. If it is a social, relationship, playful, aesthetic, or Oracle moment, make only the expression more alive; the command's actual result remains sacred.

NEVER mention algorithms, scoring systems, databases, prompts, providers, selection mechanics, internal memory, archives, monitoring, scanning, tests, debugging, placeholders, hidden logic, or how this text was generated. Never claim knowledge of a person's private feelings or unseen actions. Never use canned phrases such as 'records patterns', 'does not explain', 'conversational gravity', 'quiet pull', or 'signal:'.

GROUP/COMMAND CONTEXT:
{context[:1200]}

RECENT OUTPUT TO AVOID ECHOING:
{recent_text}

RAW AUTHORITATIVE MESSAGE:
{raw[:3200]}

Return ONLY the final Telegram text. No explanation."""

async def render(raw: str, *, command: str = "oracle", context: str = "", recent: Iterable[str] = ()) -> str:
    raw = (raw or "").strip()
    command = str(command or "oracle").lower().lstrip("/")
    if not raw or command in MECHANICAL_COMMANDS: return raw
    key = f"{context}:{command}"
    async with _LOCKS[key]:
        previous = list(_HISTORY[key])
        prompt = _prompt(raw, command, context, list(recent) + previous[-6:])
        result = ""
        try:
            async with _SEM: result = _clean(await service.generate(prompt, timeout=18.0))
        except (AIUnavailable, Exception): result = ""
        if not _safe(result, raw): result = _fallback(raw, command)
        fp = _fingerprint(result)
        if fp in _HISTORY[key]:
            result = _fallback(raw, command); fp = _fingerprint(result)
        _HISTORY[key].append(fp)
        return result

async def _send_one_message_with_gif(bot, chat_id, text: str, term: str, reply_to_message_id=None):
    from handlers.chat import get_gif_url
    from telegram.constants import ParseMode
    rendered = await render(text, command="social-action", context=f"chat:{chat_id}")
    url = await get_gif_url(term) if term else None
    if not url: return await bot.send_message(chat_id, rendered, reply_to_message_id=reply_to_message_id)
    caption = rendered[:900].rstrip() + "\n\nPowered By GIPHY"
    return await bot.send_animation(chat_id, url, caption=caption[:1024], parse_mode=ParseMode.MARKDOWN, show_caption_above_media=True, reply_to_message_id=reply_to_message_id)

class BotProxy:
    def __init__(self, bot, command: str, context: str): self._bot=bot; self._command=command; self._context=context; self._original_send_message=bot.send_message
    def __getattr__(self, name): return getattr(self._bot, name)
    async def send_message(self, chat_id, text=None, *args, **kwargs):
        rendered=await render(str(text or ""), command=self._command, context=self._context)
        return await self._original_send_message(chat_id, rendered, *args, **kwargs)

class ContextProxy:
    def __init__(self, context, command: str, expression_context: str):
        self._context=context; bot=getattr(context,"bot",None); self._bot_proxy=BotProxy(bot,command,expression_context) if bot else None
    def __getattr__(self,name):
        if name=="bot" and self._bot_proxy is not None:return self._bot_proxy
        return getattr(self._context,name)

class MessageProxy:
    def __init__(self,message,command:str,context:str): self._message=message; self._command=command; self._context=context
    def __getattr__(self,name): return getattr(self._message,name)
    async def reply_text(self,text=None,*args,**kwargs):
        rendered=await render(str(text or ""),command=self._command,context=self._context)
        return await self._message.reply_text(rendered,*args,**kwargs)

class UpdateProxy:
    def __init__(self,update,command:str,context:str): self._update=update; self._command=command; self._context=context; self._message_proxy=None
    def __getattr__(self,name):
        if name in {"effective_message","message"}:
            if self._message_proxy is None:
                message=getattr(self._update,name,None); self._message_proxy=MessageProxy(message,self._command,self._context) if message else None
            return self._message_proxy
        return getattr(self._update,name)

def wrap_callback(callback, command: str):
    if command in MECHANICAL_COMMANDS:return callback
    _install_media_bridge()
    async def wrapped(update,context):
        chat=getattr(update,"effective_chat",None); title=getattr(chat,"title",None) or getattr(chat,"type","chat")
        expression_context=f"Telegram {title}; expressive command /{command}"
        return await callback(UpdateProxy(update,command,expression_context),ContextProxy(context,command,expression_context))
    wrapped.__name__=getattr(callback,"__name__",f"oracle_{command}"); wrapped.__doc__=getattr(callback,"__doc__",None)
    return wrapped

def _install_media_bridge() -> None:
    global _MEDIA_BRIDGE_INSTALLED
    if _MEDIA_BRIDGE_INSTALLED:return
    try: import handlers.chat as chat_module
    except Exception:return
    async def send_text_with_gif(update,context,text=None,term=None):
        if hasattr(update,"message") or hasattr(update,"effective_message"):
            message=update.effective_message; chat_id=update.effective_chat.id
            return await _send_one_message_with_gif(context.bot,chat_id,text or "",term or "",getattr(message,"message_id",None))
        return await _send_one_message_with_gif(update,context,text or "",term or "")
    chat_module.send_text_with_gif=send_text_with_gif
    _MEDIA_BRIDGE_INSTALLED=True
