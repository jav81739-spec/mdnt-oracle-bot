"""Handler package bootstrap with preserved legacy command registration."""
from . import games
from core.game_runtime import persistent_game_state
from telegram.ext import Application, CommandHandler


def _install_oracle_expression_bridge() -> None:
    """Wrap expressive command callbacks without changing business mechanics."""
    try:
        from core.oracle_expression import wrap_callback, MECHANICAL_COMMANDS
    except Exception:
        return
    original = getattr(Application, "add_handler", None)
    if not original or getattr(original, "_oracle_expression_bridge", False):
        return

    def wrap_existing(application):
        for handlers in getattr(application, "handlers", {}).values():
            for handler in handlers:
                commands = getattr(handler, "commands", None) or ()
                callback = getattr(handler, "callback", None)
                if not commands or not callback or getattr(callback, "_oracle_expression_wrapped", False):
                    continue
                command = str(next(iter(commands))).lower().lstrip("/")
                if command in MECHANICAL_COMMANDS:
                    continue
                wrapped = wrap_callback(callback, command)
                if wrapped is not callback:
                    setattr(wrapped, "_oracle_expression_wrapped", True)
                    handler.callback = wrapped

    def add_handler(self, handler, *args, **kwargs):
        wrap_existing(self)
        commands = getattr(handler, "commands", None) or ()
        if commands and hasattr(handler, "callback"):
            command = str(next(iter(commands))).lower().lstrip("/")
            callback = getattr(handler, "callback", None)
            if callback and command not in MECHANICAL_COMMANDS and not getattr(callback, "_oracle_expression_wrapped", False):
                wrapped = wrap_callback(callback, command)
                if wrapped is not callback:
                    setattr(wrapped, "_oracle_expression_wrapped", True)
                    handler.callback = wrapped
        return original(self, handler, *args, **kwargs)

    add_handler._oracle_expression_bridge = True
    Application.add_handler = add_handler


_install_oracle_expression_bridge()


def _wrap(name: str, *state: str, key: str) -> None:
    """Wrap one legacy stateful game with durable per-chat storage."""
    setattr(games, name, persistent_game_state(*state, state_key=key)(getattr(games, name)))


_wrap("riddle", "active_riddles", key="riddle")
_wrap("riddle_answer", "active_riddles", key="riddle")
_wrap("scramble", "active_scrambles", key="scramble")
_wrap("unscramble", "active_scrambles", key="scramble")
_wrap("hangman", "active_hangman", key="hangman")
_wrap("hangman_guess", "active_hangman", key="hangman")
_wrap("tictactoe", "active_ttt", key="tictactoe")
_wrap("ttt_move", "active_ttt", key="tictactoe")
_wrap("wordchain_start", "active_wordchain", key="wordchain")
_wrap("chain_word", "active_wordchain", key="wordchain")
_wrap("wordle", "active_wordle", key="wordle")
_wrap("wordle_guess", "active_wordle", key="wordle")
_wrap("rock_paper_scissors", "leaderboard", key="leaderboard")
_wrap("guess_number", "leaderboard", key="leaderboard")
_wrap("leaderboard_cmd", "leaderboard", key="leaderboard")


async def _checkin(update, context):
    await update.effective_message.reply_text("☾ Check-in. How are you actually doing today?\n\nNo performance required. Just an honest answer, if you have one. 🌙")


async def _streakcheck(update, context):
    db=context.application.bot_data.get("oracle_db"); user=update.effective_user; chat=update.effective_chat
    if not db or not user or not chat:
        await update.effective_message.reply_text("☾ Your streak is quiet for now."); return
    try:
        rows=await db.fetchall("SELECT DISTINCT date(created_at) FROM mood_log WHERE user_id=? AND group_id=? ORDER BY date(created_at) DESC LIMIT 30",(user.id,chat.id)); days={str(r[0]) for r in rows}; from datetime import date,timedelta
        streak=0; day=date.today()
        while day.isoformat() in days: streak+=1; day-=timedelta(days=1)
        await update.effective_message.reply_text(f"☾ Current streak: {streak} day{'s' if streak!=1 else ''}. Keep it natural. 🌙")
    except Exception: await update.effective_message.reply_text("☾ Your streak is quiet for now.")


async def _vent(update, context):
    text=" ".join(getattr(context,"args",[]) or []).strip()
    if not text:
        await update.effective_message.reply_text("☾ Tell me what's sitting heavy. Use /vent <message>."); return
    await update.effective_message.reply_text("☾ Heard. No fixing, no judgement. You can leave it here for a while. 🌙")


def _register_legacy_surface(app) -> None:
    """Restore recoverable legacy commands without exposing private controls."""
    from . import chat, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage, deathgames
    try:
        from . import social_engine
        from midnight_oracle.generators.social_voice import voice
        original_post=social_engine._post
        async def human_post(bot,chat_id,text):
            rendered=await voice.render(text,context=f"Telegram group {chat_id}; autonomous Midnight Oracle moment",event_key=f"social:{chat_id}")
            await original_post(bot,chat_id,rendered or text)
        social_engine._post=human_post
    except Exception:
        import logging
        logging.getLogger("midnight.social").exception("SOCIAL_VOICE_INSTALL_FAILED")
    modules = {
        "chat": {"chat": ("toggle_chat",), "persona": ("set_persona",)},
        "games": {"quiz": ("quiz",), "dare": ("dare",), "rps": ("rock_paper_scissors",), "riddle": ("riddle",), "riddleanswer": ("riddle_answer",), "guess": ("guess_number",), "leaderboard": ("leaderboard_cmd",), "dice": ("dice_game",), "darts": ("darts_game",), "basketball": ("basketball_game",), "bowling": ("bowling_game",), "football": ("football_game",), "slot": ("slot_game",), "hangman": ("hangman",), "hangmanguess": ("hangman_guess",), "tictactoe": ("tictactoe",), "ttt": ("ttt_move",), "wordchain": ("wordchain_start",), "chainword": ("chain_word",), "trivia": ("trivia",), "wordle": ("wordle",), "wordleguess": ("wordle_guess",)},
        "moderation": {"mute": ("mute",), "unmute": ("unmute",), "ban": ("ban",), "kick": ("kick",), "warn": ("warn",), "warnings": ("check_warnings",), "clearwarns": ("clear_warnings",), "pin": ("pin",), "unpin": ("unpin",), "purge": ("purge",), "rules": ("show_rules",), "setrules": ("set_rules",), "lock": ("lock",), "unlock": ("unlock",)},
        "utility": {"id": ("get_id",), "info": ("user_info",), "remind": ("remind",), "groupinfo": ("group_info",), "afk": ("set_afk",), "report": ("report",)},
        "aesthetic": {"aura": ("aura_command",), "vibecheck": ("vibecheck_command",), "identity": ("identity_command",), "shadow": ("shadow_command",), "element": ("element_command",), "corecode": ("corecode_command",), "universe": ("universe_command",), "ritual": ("ritual_command",), "duality": ("duality_command",), "nightreport": ("nightreport_command",), "sigil": ("sigil_command",), "glitch": ("glitch_command",)},
        "friendship": {"bestie": ("bestie",), "duo": ("duo",), "friendship": ("friendship_score",), "ship": ("ship",), "tagbestie": ("tag_bestie",), "squad": ("squad",), "loyalty": ("loyalty",), "hug": ("hug",), "pat": ("pat",), "highfive": ("highfive",), "slap": ("slap",), "kiss": ("kiss",), "poke": ("poke",), "cuddle": ("cuddle",), "wave": ("wave",), "bite": ("bite",), "tickle": ("tickle",)},
        "fun": {"roast": ("roast",), "compliment": ("compliment",), "8ball": ("eight_ball",), "vibe": ("vibe",), "quote": ("quote",), "poll": ("poll",), "rank": ("rank",), "ratethis": ("rate_this",), "impostor": ("impostor_start",), "revealimpostor": ("impostor_reveal",)},
        "matchmaking": {"crush": ("set_crush",), "clearcrush": ("clear_crush",), "randomship": ("random_ship",), "secretadmirer": ("secret_admirer",), "matchmaker": ("matchmaker",)},
        "stats": {"stats": ("stats",), "topactive": ("top_active",), "msgcount": ("msg_count",)},
        "events": {"joined": ("show_joined",), "left": ("show_left",), "setwelcome": ("set_welcome",), "setgoodbye": ("set_goodbye",), "invite": ("get_invite",)},
        "economy": {"daily": ("daily",), "balance": ("balance",), "rob": ("rob",), "gamble": ("gamble",), "richest": ("economy_leaderboard",), "coinboard": ("economy_leaderboard",)},
        "timecapsule": {"timecapsule": ("timecapsule",), "capsules": ("list_capsules",)},
        "marriage": {"marry": ("marry",), "accept": ("accept",), "divorce": ("divorce",), "profile": ("profile",), "work": ("work",), "chests": ("chests",), "shop": ("shop",), "buy": ("buy",), "inventory": ("inventory",), "gift": ("gift",), "cgift": ("gift",), "settings": ("settings",)},
        "deathgames": {"survive": ("survive",), "revive": ("revive",), "deathstatus": ("deathstatus",), "roulette": ("roulette",), "deathgame": ("deathgame",), "joingame": ("joingame",), "startround": ("startround",), "kill": ("kill",), "vote": ("vote",), "endgame": ("endgame",)},
    }
    module_objs={"chat":chat,"games":games,"moderation":moderation,"utility":utility,"aesthetic":aesthetic,"friendship":friendship,"fun":fun,"matchmaking":matchmaking,"stats":stats,"events":events,"economy":economy,"timecapsule":timecapsule,"marriage":marriage,"deathgames":deathgames}
    existing={str(c).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
    skip={"start","help","oracle","truth","memory","mymemory","forget","quiet","wake","house","tod","wyr","nhie","scramble","predict","predictions"}
    for module_name, command_map in modules.items():
        for command,candidates in command_map.items():
            if command in existing or command in skip: continue
            module=module_objs[module_name]; callback=next((getattr(module,name,None) for name in candidates if callable(getattr(module,name,None))),None)
            if callback: app.add_handler(CommandHandler(command,callback),group=0); existing.add(command)
    for command,callback in {"checkin":_checkin,"streakcheck":_streakcheck,"vent":_vent}.items():
        if command not in existing: app.add_handler(CommandHandler(command,callback),group=0); existing.add(command)


_legacy_wrapped=False

def register_legacy_surface(app) -> None:
    global _legacy_wrapped
    if _legacy_wrapped:return
    _legacy_wrapped=True
    try:_register_legacy_surface(app)
    except Exception:
        _legacy_wrapped=False
        raise


from . import friend_engine as _friend_engine
_original_friend_register=_friend_engine.register


def _friend_register_with_legacy(app):
    register_legacy_surface(app)
    try:
        from .relationship_engine import register as register_relationships
        register_relationships(app)
    except Exception:
        import logging
        logging.getLogger("midnight.relationship").exception("RELATIONSHIP_ENGINE_REGISTRATION_FAILED")
    return _original_friend_register(app)

_friend_engine.register=_friend_register_with_legacy

try:
    import legacy_bot as _legacy_bot
    from . import deathgames_v2 as _deathgames_v2
    _legacy_bot.deathgames = _deathgames_v2
except Exception:
    pass
