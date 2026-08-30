"""Executable member-facing social interaction aliases.

The premium help archive only exposes commands that are actually registered.
These commands intentionally use the existing friendship action engine rather
than duplicating behaviour in legacy_bot.py.
"""
from telegram.ext import CommandHandler
from handlers import friendship

SOCIAL_ACTIONS=(
    "hug","kiss","pat","kick","slap","punch","highfive","cuddle",
    "poke","bonk","bite","wave","wink","dance","roast","cheer",
    "comfort","tickle","salute","stare","handshake","fistbump",
    "shoulderpat","cheers",
)

def register(app):
    existing={str(c).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
    added=[]
    for command in SOCIAL_ACTIONS:
        callback=getattr(friendship,command,None)
        if command not in existing and callable(callback):
            app.add_handler(CommandHandler(command,callback),group=-24)
            existing.add(command);added.append(command)
    return added
