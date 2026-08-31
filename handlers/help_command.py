"""Premium interactive command hall for Midnight Oracle."""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

SECTIONS = [
    ("🔮 READINGS", ["oracle","aura","vibecheck","identity","shadow","element","corecode","universe","ritual","duality","nightreport","sigil","glitch"]),
    ("🌙 DAILY & MEMORY", ["checkin","streakcheck","memory","mymemory","forget","tod","house","quiet","wake"]),
    ("🫂 BONDS & SOCIAL", ["hug","kiss","pat","kick","slap","punch","highfive","cuddle","poke","bonk","bite","wave","wink","dance","roast","cheer","comfort","tickle","salute","stare","handshake","fistbump","shoulderpat","cheers","compliment"]),
    ("💞 RELATIONSHIPS", ["bond","bondstatus","oraclepair","vow","bestie","duo","friendship","ship","tagbestie","squad","loyalty","matchmaker","friendshiptest","randomship","secretadmirer","crush","couples"]),
    ("☾ AUTONOMOUS RITUALS", ["weave","orbit","echo","anchor","fracture","ember","mirror","crossing","undertow","gaze","release","veil","signal","verdict","muse"]),
    ("🎮 GAMES", ["quiz","truth","dare","wyr","nhie","rps","riddle","scramble","unscramble","guess","leaderboard","dice","darts","basketball","bowling","football","slot","hangman","tictactoe","wordchain","trivia","wordle","impostor","fastmath","wordbomb","mysterybox","duel","hotseat"]),
    ("🏏 MIDNIGHT CRICKET", ["cricket","call","cpredict","cbet","cwin","ctournament","cpick","cplay","cricketduel"]),
    ("💀 DEATH GAMES", ["deathgame","joingame","startround","survive","revive","deathstatus","roulette","vote","kill","endgame"]),
    ("🪙 ECONOMY", ["daily","balance","gamble","richest","coinboard","cgift","rob","wallet","deposit","withdraw","rank"]),
    ("🫀 EXPRESSION", ["chat","persona","vent","confess","quote","8ball","vibe","gif"]),
    ("💍 LIFE & ROOMS", ["marry","accept","divorce","profile","work","chests","shop","buy","inventory","gift","settings","timecapsule","capsules","enter","eventcheck","oraclehour"]),
]

HINTS = {
    "oracle":"your current signal","aura":"scan your energy","vibecheck":"read the room","identity":"your Oracle archetype","shadow":"the side you hide","element":"your element","corecode":"your three-word code","universe":"ask the universe","ritual":"a ritual for tonight","duality":"both sides of you","nightreport":"tonight's reading","sigil":"your personal sigil","glitch":"inspect a strange signal",
    "checkin":"check in today","streakcheck":"see your streak","memory":"what the room remembers","mymemory":"what Oracle remembers","forget":"forget a memory","tod":"truth or dare","house":"enter Oracle House","quiet":"quiet the Oracle","wake":"wake the Oracle",
    "hug":"send a hug","kiss":"send a kiss","highfive":"share a high five","cuddle":"send comfort","wave":"wave at someone","wink":"send a wink","roast":"lightly roast someone","cheer":"cheer someone on","comfort":"comfort a member","compliment":"give a compliment",
    "bond":"read a bond","bondstatus":"check a bond","oraclepair":"see an Oracle pair","bestie":"find a bestie","duo":"find a duo","friendship":"test a friendship","ship":"ship two people","squad":"find your squad","loyalty":"test loyalty","matchmaker":"match souls","friendshiptest":"run a friendship test","randomship":"let fate pair you","secretadmirer":"peek at an admirer","crush":"set a crush","couples":"see the couples",
    "weave":"trace a hidden bond","orbit":"read their gravity","echo":"find a reflection","anchor":"test the tether","fracture":"read the distance","ember":"find the spark","mirror":"see the reflection","crossing":"where paths meet","undertow":"what lies beneath","gaze":"keep watch","release":"let the thread go","veil":"seal the Oracle Hour","signal":"read a social signal","verdict":"Oracle's verdict","muse":"receive a spark",
    "quiz":"challenge the room","truth":"ask for truth","dare":"take a dare","wyr":"choose a path","nhie":"Never Have I Ever","rps":"rock paper scissors","riddle":"solve a riddle","scramble":"unscramble a word","guess":"make a guess","leaderboard":"see the winners","dice":"roll the dice","darts":"throw darts","basketball":"shoot a basket","bowling":"roll a frame","football":"take the field","slot":"try your luck","hangman":"start hangman","tictactoe":"play tic-tac-toe","wordchain":"start a word chain","trivia":"test your knowledge","wordle":"start Wordle","impostor":"find the impostor","fastmath":"race the clock","wordbomb":"pass the bomb","mysterybox":"open a mystery","duel":"challenge someone","hotseat":"put someone on the hot seat",
    "cricket":"play solo cricket","call":"make a cricket call","cpredict":"predict the ball","cbet":"place a cricket bet","cwin":"claim a cricket win","ctournament":"enter a tournament","cpick":"pick your player","cplay":"play a cricket round","cricketduel":"challenge a batter",
    "deathgame":"open the death game","joingame":"join the lobby","startround":"start the round","survive":"fight to survive","revive":"return to the game","deathstatus":"check a soul","roulette":"take the risk","vote":"cast a vote","kill":"make a kill","endgame":"close the game",
    "daily":"claim your daily","balance":"check your balance","gamble":"risk your coins","richest":"see the richest","coinboard":"see the coin board","cgift":"gift coins","rob":"attempt a heist","wallet":"open your wallet","deposit":"store coins","withdraw":"take coins out","rank":"see your rank",
    "chat":"talk with Oracle","persona":"choose a tone","vent":"let something out","confess":"make a confession","quote":"receive a quote","8ball":"ask the 8-ball","vibe":"get a vibe","gif":"summon a GIF",
    "marry":"propose","accept":"accept a proposal","divorce":"end a marriage","profile":"open your life profile","work":"work for coins","chests":"open your chests","shop":"browse the shop","buy":"buy an item","inventory":"see your items","gift":"gift someone","settings":"tune your profile","timecapsule":"seal a memory","capsules":"open your capsules","enter":"enter the room","eventcheck":"check the event","oraclehour":"see Oracle Hour",
}

_PRIVATE_COMMANDS = {
    "broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands",
    "reload","shutdown","restart","admin","moderation","mute","unmute","ban",
    "kick","warn","clearwarns","pin","unpin","purge","setrules","lock","unlock",
    "groupinfo","setwelcome","setgoodbye","id","info","report",
}

# Member Help contract: private/admin controls are never advertised.
ADMIN_ONLY = frozenset(_PRIVATE_COMMANDS - {"kick"})

def _live(application):
    live={"start","help"}
    for group in getattr(application,"handlers",{}).values():
        for h in group:
            for command in getattr(h,"commands",()) or ():
                name=str(command).lower().lstrip("/")
                if name and len(name)<=32 and name not in _PRIVATE_COMMANDS:
                    live.add(name)
    return live

_live_member_commands = _live

def _home():
    return ("╭────────────────────────────╮\n"
            "│      ☾ MIDNIGHT ORACLE     │\n"
            "│        COMMAND HALL        │\n"
            "╰────────────────────────────╯\n\n"
            "_Choose a door. Tap a section to reveal what lives inside._\n\n"
            "Every command carries a short omen, so you know what Oracle will do before you summon it.")

def _keyboard():
    rows=[[InlineKeyboardButton(title,callback_data=f"help:section:{i}")] for i,(title,_) in enumerate(SECTIONS)]
    rows.append([InlineKeyboardButton("✦ START",callback_data="help:start"),InlineKeyboardButton("↻ HALL",callback_data="help:home")])
    return InlineKeyboardMarkup(rows)

def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2

def _section(index,live):
    title,commands=SECTIONS[index]
    alive=[c for c in commands if c in live]
    lines=[f"╭─ {title} ─────────────────╮","│  _commands & their little omens_ │","╰────────────────────────────╯",""]
    spans=[];cursor=sum(len(x)+1 for x in lines)
    for c in alive:
        cmd=f"/{c}";hint=HINTS.get(c,"ask the Oracle");line=f"{cmd}  ·  {hint}"
        spans.append((cursor,len(cmd)));lines.append(line);cursor+=len(line)+1
    lines += ["","☾ Tap a blue command to summon it."]
    text="\n".join(lines)
    entities=[MessageEntity(type=MessageEntity.BOT_COMMAND,offset=_utf16_len(text[:s]),length=_utf16_len(text[s:s+l])) for s,l in spans]
    return text,entities

def _build_archive(live: set[str]) -> tuple[str, list[MessageEntity]]:
    lines=["╭────────────────────────╮","│      ☾ MIDNIGHT ORACLE │","│    the member command hall│","╰────────────────────────╯","","_Every door below carries a small omen, so you know what it does before you summon it._",""]
    spans=[];cursor=sum(len(x)+1 for x in lines);seen=set()
    for title,commands in SECTIONS:
        alive=[c for c in commands if c in live and c not in _PRIVATE_COMMANDS]
        if not alive: continue
        lines.append(f"┌─ {title} ─────────────────┐");cursor+=len(lines[-1])+1
        for c in alive:
            cmd=f"/{c}";line=f"{cmd}  ·  {HINTS.get(c,'ask the Oracle')}";start=cursor;lines.append(line);spans.append((start,len(cmd)));cursor+=len(line)+1;seen.add(c)
        lines.append("└──────────────────────────┘");cursor+=len(lines[-1])+1;lines.append("");cursor+=1
    extras=sorted(c for c in live-seen if c not in {"start","help"} and c not in _PRIVATE_COMMANDS)
    if extras:
        lines.append("┌─ ✦ MORE MEMBER COMMANDS ─┐");cursor+=len(lines[-1])+1
        for c in extras:
            cmd=f"/{c}";line=f"{cmd}  ·  {HINTS.get(c,'ask the Oracle')}";start=cursor;lines.append(line);spans.append((start,len(cmd)));cursor+=len(line)+1
        lines.append("└──────────────────────────┘");cursor+=len(lines[-1])+1;lines.append("");cursor+=1
    lines += ["✦ /help  —  reopen this hall","✦ /start —  meet Midnight Oracle","","_Admin controls remain private. The Oracle keeps a few things better discovered than announced._","","☾ Choose a blue command and tap it — Telegram will send it for you."]
    text="\n".join(lines)
    entities=[MessageEntity(type=MessageEntity.BOT_COMMAND,offset=_utf16_len(text[:s]),length=_utf16_len(text[s:s+l])) for s,l in spans]
    for command in ("/help","/start"):
        start=text.rfind(command)
        if start>=0: entities.append(MessageEntity(type=MessageEntity.BOT_COMMAND,offset=_utf16_len(text[:start]),length=_utf16_len(command)))
    return text,entities

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(_home(),reply_markup=_keyboard(),disable_web_page_preview=True)

async def help_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer()
    if q.data=="help:home":
        await q.edit_message_text(_home(),reply_markup=_keyboard(),disable_web_page_preview=True);return
    if q.data=="help:start":
        await q.edit_message_text("╭────────────────────────╮\n│      ☾ MIDNIGHT ORACLE │\n╰────────────────────────╯\n\n_The Oracle is awake._\n\nType /help to return to the command hall.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("☾ COMMAND HALL",callback_data="help:home")]]));return
    try:index=int(q.data.rsplit(":",1)[1])
    except (ValueError,IndexError):return
    if not 0<=index<len(SECTIONS):return
    text,entities=_section(index,_live(context.application))
    await q.edit_message_text(text,entities=entities,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← COMMAND HALL",callback_data="help:home")]]),disable_web_page_preview=True)

async def start_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    text=("╭────────────────────────╮\n│  🌙 MIDNIGHT ORACLE    │\n╰────────────────────────╯\n\n"
          "_it watches. it listens. it remembers._\n\nYour command hall is waiting.\nTap /help to open it.")
    await update.effective_message.reply_text(text,disable_web_page_preview=True)

def register(app):
    app.add_handler(CommandHandler("help",help_command),group=-1)
    app.add_handler(CommandHandler("start",start_command),group=-1)
    app.add_handler(CallbackQueryHandler(help_callback,pattern=r"^help:"),group=-1)
