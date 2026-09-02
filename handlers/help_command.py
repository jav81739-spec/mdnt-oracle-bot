"""Premium, member-facing command archive for Midnight Oracle."""
from __future__ import annotations

from telegram import MessageEntity, Update
from telegram.ext import ContextTypes, CommandHandler

ADMIN_ONLY = {
    "broadcast", "announce", "midnightmap", "ownerstatus", "ownerstats",
    "setcommands", "reload", "shutdown", "restart", "admin", "moderation",
    "mute", "unmute", "ban", "kick", "warn", "clearwarns", "pin", "unpin",
    "purge", "setrules", "lock", "unlock", "groupinfo", "setwelcome", "setgoodbye",
}
_PRIVATE_COMMANDS = frozenset(ADMIN_ONLY)

SECTIONS = [
    ("🔮 READINGS", ["oracle", "aura", "vibecheck", "identity", "shadow", "element", "corecode", "universe", "ritual", "duality", "nightreport", "sigil", "glitch"]),
    ("🌙 DAILY & MEMORY", ["checkin", "streakcheck", "memory", "mymemory", "forget", "tod", "house", "quiet", "wake"]),
    ("🫂 BONDS & SOCIAL", ["hug", "kiss", "pat", "kick", "slap", "punch", "highfive", "cuddle", "poke", "bonk", "bite", "wave", "wink", "dance", "roast", "cheer", "comfort", "tickle", "salute", "stare", "handshake", "fistbump", "shoulderpat", "cheers", "compliment"]),
    ("💞 RELATIONSHIPS", ["bond", "bondstatus", "oraclepair", "vow", "bestie", "duo", "friendship", "ship", "tagbestie", "squad", "loyalty", "matchmaker", "randomship", "secretadmirer", "crush", "couples"]),
    ("🪞 ORACLE SIGNALS", ["weave", "orbit", "echo", "anchor", "fracture", "ember", "mirror", "crossing", "undertow", "gaze", "release", "veil", "signal", "verdict", "muse"]),
    ("🎮 GAMES", ["quiz", "truth", "dare", "wyr", "nhie", "rps", "riddle", "riddleanswer", "scramble", "unscramble", "guess", "leaderboard", "dice", "darts", "basketball", "bowling", "football", "slot", "hangman", "hangmanguess", "tictactoe", "ttt", "wordchain", "chainword", "trivia", "wordle", "wordleguess", "ratethis", "impostor", "revealimpostor", "fastmath", "wordbomb", "mysterybox", "duel", "hotseat"]),
    ("🏏 MIDNIGHT CRICKET", ["cricket", "call", "cpredict", "cbet", "cwin", "ctournament", "cpick", "cplay", "cricketduel"]),
    ("💀 DEATH GAMES", ["deathgame", "joingame", "startround", "survive", "revive", "deathstatus", "roulette", "vote", "kill", "endgame"]),
    ("🪙 ECONOMY", ["daily", "balance", "gamble", "richest", "coinboard", "cgift", "rob", "wallet", "deposit", "withdraw", "rank"]),
    ("🫀 EXPRESSION", ["chat", "persona", "vent", "confess", "quote", "8ball", "vibe", "gif"]),
    ("💍 LIFE & ROOMS", ["marry", "accept", "divorce", "profile", "work", "chests", "shop", "buy", "inventory", "gift", "settings", "timecapsule", "capsules", "enter", "eventcheck", "oraclehour"]),
]

HINTS = {"start": "meet the Oracle", "help": "open this command archive", "oracle": "read your current signal", "aura": "scan your energy", "vibecheck": "check the room's vibe", "identity": "discover your Oracle archetype", "shadow": "meet the side you hide", "element": "find your element", "corecode": "reveal your three-word code", "universe": "ask the universe", "ritual": "receive a ritual", "duality": "read both sides of you", "nightreport": "see tonight's reading", "sigil": "draw your personal sigil", "glitch": "inspect the strange signal", "checkin": "check in for the day", "streakcheck": "see your streak", "memory": "ask what the room remembers", "mymemory": "see what Oracle remembers", "forget": "ask Oracle to forget", "tod": "open truth or dare", "house": "enter Oracle House", "quiet": "quiet the Oracle", "wake": "wake the Oracle", "hug": "send someone a hug", "kiss": "send a kiss", "pat": "give a gentle pat", "highfive": "share a high five", "cuddle": "send comfort", "wave": "wave at someone", "wink": "send a wink", "roast": "lightly roast someone", "cheer": "cheer someone on", "comfort": "comfort a member", "compliment": "give someone a compliment", "bond": "read a bond", "bondstatus": "check a bond", "bestie": "find a bestie", "duo": "find a duo", "friendship": "read a friendship", "ship": "ship two people", "tagbestie": "call your bestie", "squad": "find your squad", "loyalty": "read loyalty", "matchmaker": "let Oracle match souls", "randomship": "leave the pairing to fate", "secretadmirer": "peek at a secret admirer", "crush": "set a crush", "couples": "see the couples", "signal": "read a social signal", "verdict": "ask for Oracle's verdict", "muse": "receive a spark", "quiz": "challenge the room", "truth": "ask for truth", "dare": "take a dare", "wyr": "choose between two paths", "nhie": "play never have I ever", "rps": "play rock paper scissors", "riddle": "solve a riddle", "riddleanswer": "answer the riddle", "scramble": "unscramble the word", "unscramble": "solve the scramble", "guess": "make a guess", "leaderboard": "see the winners", "dice": "roll the dice", "darts": "throw darts", "basketball": "shoot a basket", "bowling": "roll a frame", "football": "take the field", "slot": "try the slots", "hangman": "start hangman", "hangmanguess": "guess a letter", "tictactoe": "start tic-tac-toe", "ttt": "make your move", "wordchain": "start a word chain", "chainword": "continue the chain", "trivia": "challenge your knowledge", "wordle": "start wordle", "wordleguess": "make a wordle guess", "ratethis": "rate the room's choice", "impostor": "find the impostor", "revealimpostor": "reveal the impostor", "fastmath": "race the clock", "wordbomb": "pass the word bomb", "mysterybox": "open a mystery", "duel": "challenge someone", "hotseat": "put someone on the hot seat", "cricket": "play solo cricket", "cricketduel": "challenge a batter", "call": "make a cricket call", "cpredict": "predict the ball", "cbet": "place a cricket bet", "cwin": "claim a cricket win", "ctournament": "enter a tournament", "cpick": "pick your player", "cplay": "play a cricket round", "deathgame": "open the death game", "joingame": "join the lobby", "startround": "start the round", "survive": "fight to survive", "revive": "return to the game", "deathstatus": "check a soul", "roulette": "take the risk", "vote": "cast a vote", "kill": "make a kill", "endgame": "close the game", "daily": "claim your daily", "balance": "check your balance", "gamble": "risk your coins", "richest": "see the richest", "coinboard": "see the coin board", "cgift": "gift some coins", "rob": "attempt a heist", "wallet": "open your wallet", "deposit": "store your coins", "withdraw": "take coins out", "rank": "see your rank", "chat": "talk with Oracle", "persona": "choose your Oracle tone", "vent": "let something out", "confess": "make a confession", "quote": "receive a quote", "8ball": "ask the 8-ball", "vibe": "get a vibe", "gif": "summon a GIF", "marry": "propose", "accept": "accept a proposal", "divorce": "end a marriage", "profile": "open a life profile", "work": "work for coins", "chests": "open your chests", "shop": "browse the shop", "buy": "buy an item", "inventory": "see your items", "gift": "gift someone", "settings": "tune your profile", "timecapsule": "seal a memory", "capsules": "open your capsules", "enter": "enter the current room", "eventcheck": "check the event", "oraclehour": "see Oracle Hour"}


def _live_member_commands(application) -> set[str]:
    live = {"start", "help"}
    for handlers in getattr(application, "handlers", {}).values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                for command in getattr(handler, "commands", ()):
                    name = str(command).lower().lstrip("/")
                    if name and name not in ADMIN_ONLY and name != "friendshiptest" and len(name) <= 32:
                        live.add(name)
    return live


def _section(group_index: int, live: set[str]) -> tuple[str, list[MessageEntity]]:
    """Compatibility view of one member-help section used by regression checks."""
    if group_index < 0 or group_index >= len(SECTIONS):
        return "", []
    title, commands = SECTIONS[group_index]
    selected = [c for c in commands if c in live and c not in ADMIN_ONLY]
    lines = [f"┌─ {title} ─────────────────┐"]
    for command in selected:
        lines.append(f"/{command}  —  {HINTS.get(command, 'ask the Oracle')}")
    lines.append("└──────────────────────────┘")
    return "\n".join(lines), []


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _build_archive(live: set[str]) -> tuple[str, list[MessageEntity]]:
    lines: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    def push(line: str) -> None:
        nonlocal cursor
        lines.append(line); cursor += len(line) + 1
    def push_command(command: str) -> None:
        nonlocal cursor
        text = f"/{command}"; start = cursor
        push(text + f"  —  {HINTS.get(command, 'ask the Oracle')}")
        spans.append((start, len(text)))
    push("╭────────────────────────╮"); push("│  🌙 MIDNIGHT ORACLE    │"); push("│  the member command hall│"); push("╰────────────────────────╯"); push("")
    push("_Every door below is manually triggered. Some answer with words; some may answer with a little visual magic._"); push("")
    known: set[str] = set()
    for title, commands in SECTIONS:
        alive = [c for c in commands if c in live]
        if not alive: continue
        push(f"┌─ {title} ─────────────────┐")
        for command in alive: push_command(command); known.add(command)
        push("└──────────────────────────┘"); push("")
    extras = sorted(c for c in live - known if c not in {"start", "help", "friendshiptest"})
    if extras:
        push("┌─ ✦ MORE MEMBER COMMANDS ─┐")
        for command in extras: push_command(command)
        push("└──────────────────────────┘"); push("")
    push("✦ /help  —  reopen this hall"); push("✦ /start —  meet Midnight Oracle"); push(""); push("_Admin controls remain private. The Oracle keeps a few things better discovered than announced._"); push(""); push("☾  Choose a blue command and tap it — Telegram will send it for you.")
    text = "\n".join(lines)
    entities = [MessageEntity(type=MessageEntity.BOT_COMMAND, offset=_utf16_len(text[:start]), length=_utf16_len(text[start:start + length])) for start, length in spans]
    for command in ("/help", "/start"):
        start = text.rfind(command)
        if start >= 0: entities.append(MessageEntity(type=MessageEntity.BOT_COMMAND, offset=_utf16_len(text[:start]), length=_utf16_len(command)))
    return text, entities


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, entities = _build_archive(_live_member_commands(context.application))
    try: await update.effective_message.reply_text(text, entities=entities, disable_web_page_preview=True)
    except Exception: await update.effective_message.reply_text(text)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type == "private":
        text = "╭────────────────────────╮\n│  🌙 MIDNIGHT ORACLE    │\n╰────────────────────────╯\n\n_hello._\n\nYour command hall is waiting.\nTap /help to open it — every listed command is meant to be used."
    else:
        text = "╭────────────────────────╮\n│  🌙 MIDNIGHT ORACLE    │\n╰────────────────────────╯\n\n_the room has a new presence._\n\nTap /help for the member command hall."
    try: await update.effective_message.reply_text(text, disable_web_page_preview=True)
    except Exception: await update.effective_message.reply_text(text)


def register(app):
    app.add_handler(CommandHandler("help", help_command), group=-1)
    app.add_handler(CommandHandler("start", start_command), group=-1)
