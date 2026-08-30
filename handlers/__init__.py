"""Handler package bootstrap with preserved legacy command registration."""
from . import games
from core.game_runtime import persistent_game_state
from telegram.ext import CommandHandler


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


def _register_legacy_surface(app) -> None:
    """Restore the pre-rebuild public command surface without exposing private controls."""
    from . import chat, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage, deathgames
    modules = {
        "chat": {"chat": ("toggle_chat",), "persona": ("set_persona",)},
        "games": {
            "quiz": ("quiz",), "dare": ("dare",), "rps": ("rock_paper_scissors",),
            "riddle": ("riddle",), "riddleanswer": ("riddle_answer",), "guess": ("guess_number",),
            "leaderboard": ("leaderboard_cmd",), "dice": ("dice_game",), "darts": ("darts_game",),
            "basketball": ("basketball_game",), "bowling": ("bowling_game",), "football": ("football_game",),
            "slot": ("slot_game",), "hangman": ("hangman",), "hangmanguess": ("hangman_guess",),
            "tictactoe": ("tictactoe",), "ttt": ("ttt_move",), "wordchain": ("wordchain_start",),
            "chainword": ("chain_word",), "trivia": ("trivia",), "wordle": ("wordle",), "wordleguess": ("wordle_guess",),
        },
        "moderation": {"mute": ("mute",), "unmute": ("unmute",), "ban": ("ban",), "kick": ("kick",), "warn": ("warn",), "warnings": ("check_warnings",), "clearwarns": ("clear_warnings",), "pin": ("pin",), "unpin": ("unpin",), "purge": ("purge",), "rules": ("show_rules",), "setrules": ("set_rules",), "lock": ("lock",), "unlock": ("unlock",)},
        "utility": {"id": ("get_id",), "info": ("user_info",), "remind": ("remind",), "groupinfo": ("group_info",), "afk": ("set_afk",), "report": ("report",)},
        "aesthetic": {"aura": ("aura_command",), "vibecheck": ("vibecheck_command",), "identity": ("identity_command",), "shadow": ("shadow_command",), "element": ("element_command",), "corecode": ("corecode_command",), "universe": ("universe_command",), "ritual": ("ritual_command",), "duality": ("duality_command",), "nightreport": ("nightreport_command",), "sigil": ("sigil_command",), "glitch": ("glitch_command",)},
        "friendship": {"bestie": ("bestie",), "duo": ("duo",), "friendship": ("friendship_score",), "ship": ("ship",), "tagbestie": ("tag_bestie",), "squad": ("squad",), "loyalty": ("loyalty",), "friendshiptest": ("friendship_test",), "hug": ("hug",), "pat": ("pat",), "highfive": ("highfive",), "slap": ("slap",), "kiss": ("kiss",), "poke": ("poke",), "cuddle": ("cuddle",), "wave": ("wave",), "bite": ("bite",), "tickle": ("tickle",)},
        "fun": {"roast": ("roast",), "compliment": ("compliment",), "8ball": ("eight_ball",), "vibe": ("vibe",), "quote": ("quote",), "poll": ("poll",), "rank": ("rank",), "ratethis": ("rate_this",), "impostor": ("impostor_start",), "revealimpostor": ("impostor_reveal",)},
        "matchmaking": {"crush": ("set_crush",), "clearcrush": ("clear_crush",), "randomship": ("random_ship",), "secretadmirer": ("secret_admirer",), "matchmaker": ("matchmaker",)},
        "stats": {"stats": ("stats",), "topactive": ("top_active",), "msgcount": ("msg_count",)},
        "events": {"joined": ("show_joined",), "left": ("show_left",), "setwelcome": ("set_welcome",), "setgoodbye": ("set_goodbye",), "invite": ("get_invite",)},
        "economy": {"daily": ("daily",), "balance": ("balance",), "rob": ("rob",), "gamble": ("gamble",), "richest": ("economy_leaderboard",)},
        "timecapsule": {"timecapsule": ("timecapsule",), "capsules": ("list_capsules",)},
        "marriage": {"marry": ("marry",), "accept": ("accept",), "divorce": ("divorce",), "profile": ("profile",), "work": ("work",), "chests": ("chests",), "shop": ("shop",), "buy": ("buy",), "inventory": ("inventory",), "gift": ("gift",), "settings": ("settings",)},
        "deathgames": {"survive": ("survive",), "revive": ("revive",), "deathstatus": ("deathstatus",), "roulette": ("roulette",), "deathgame": ("deathgame",), "joingame": ("joingame",), "startround": ("startround",), "kill": ("kill",), "vote": ("vote",), "endgame": ("endgame",)},
    }
    module_objs = {"chat":chat,"games":games,"moderation":moderation,"utility":utility,"aesthetic":aesthetic,"friendship":friendship,"fun":fun,"matchmaking":matchmaking,"stats":stats,"events":events,"economy":economy,"timecapsule":timecapsule,"marriage":marriage,"deathgames":deathgames}
    existing = {str(c).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for h in hs for c in (getattr(h,"commands",None) or ())}
    skip = {"start","help","oracle","truth","memory","mymemory","forget","quiet","wake","house","tod","wyr","nhie","scramble","predict","predictions"}
    for module_name, command_map in modules.items():
        module = module_objs[module_name]
        for command, candidates in command_map.items():
            if command in existing or command in skip:
                continue
            callback = next((getattr(module, name, None) for name in candidates if callable(getattr(module, name, None))), None)
            if callback:
                app.add_handler(CommandHandler(command, callback), group=0)
                existing.add(command)


_legacy_wrapped = False

def register_legacy_surface(app) -> None:
    """Register all recoverable legacy commands exactly once."""
    global _legacy_wrapped
    if _legacy_wrapped:
        return
    _legacy_wrapped = True
    _register_legacy_surface(app)


# The production entrypoint invokes handlers.friend_engine.register during post-init.
# Wrap that registration point so the complete legacy command surface is restored
# before the canonical Phase-1/3/4 commands are attached.
from . import friend_engine as _friend_engine
_original_friend_register = _friend_engine.register

def _friend_register_with_legacy(app):
    """Attach legacy commands before the existing friend-engine registration."""
    register_legacy_surface(app)
    return _original_friend_register(app)

_friend_engine.register = _friend_register_with_legacy
