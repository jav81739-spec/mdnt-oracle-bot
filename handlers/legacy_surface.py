"""Live legacy command surface for the canonical Midnight Oracle runtime.

This module wires callbacks that already exist into the rebuild Application.
Member-facing command names are kept clean: internal diagnostics or test-style
surfaces are never registered as Telegram commands.
"""
from __future__ import annotations

import logging
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

import legacy_bot
from handlers import chat, games, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage, deathgames_v2 as deathgames
from handlers import economy_compat, deathgames_hardened, legacy_economy_atomic

# The betting/vault surface still intentionally uses its legacy key namespace.
# Harden its read-modify-write helpers before callbacks are registered, without
# changing the command names or the legacy data format.
legacy_economy_atomic.harden(legacy_bot)

log = logging.getLogger("midnight.legacy_surface")


def _assert_no_duplicate_declarations(modules: dict[str, dict[str, str]], direct: dict[str, str]) -> None:
    """Fail fast when two registration surfaces claim the same command."""
    owners: dict[str, str] = {}
    for module_name, commands in modules.items():
        for command in commands:
            name = command.lower().lstrip("/")
            previous = owners.get(name)
            if previous and previous != module_name:
                raise RuntimeError(f"COMMAND_OWNER_COLLISION: /{name} ({previous} vs {module_name})")
            owners[name] = module_name
    for command in direct:
        name = command.lower().lstrip("/")
        previous = owners.get(name)
        if previous and previous != "direct":
            raise RuntimeError(f"COMMAND_OWNER_COLLISION: /{name} ({previous} vs direct)")
        owners[name] = "direct"


def _callback(target, name: str):
    cb = getattr(target, name, None)
    return cb if callable(cb) else None


def _add_command(app, existing: set[str], command: str, target, callback_name: str, *, group: int = 0) -> bool:
    name = command.lower().lstrip("/")
    if name in existing:
        return False
    callback = _callback(target, callback_name)
    if callback is None:
        log.warning("LEGACY_COMMAND_UNAVAILABLE | command=/%s | callback=%s.%s", name, getattr(target, "__name__", target), callback_name)
        return False
    app.add_handler(CommandHandler(name, callback), group=group)
    existing.add(name)
    return True


def register_legacy_surface(app) -> dict[str, object]:
    existing = {
        str(command).lower().lstrip("/")
        for handlers in getattr(app, "handlers", {}).values()
        for handler in handlers
        for command in (getattr(handler, "commands", None) or ())
    }
    reserved = {
        "start", "help", "oracle", "truth", "memory", "mymemory", "forget",
        "tod", "wyr", "nhie", "scramble", "unscramble", "predict", "predictions",
        "house", "quiet", "wake",
    }
    module_map = {
        "chat": chat, "games": games, "moderation": moderation, "utility": utility,
        "aesthetic": aesthetic, "friendship": friendship, "fun": fun,
        "matchmaking": matchmaking, "stats": stats, "events": events,
        "economy": economy, "timecapsule": timecapsule, "marriage": marriage,
        "deathgames": deathgames,
    }
    module_commands = {
        "chat": {"chat": "toggle_chat", "persona": "set_persona"},
        "games": {"quiz": "quiz", "dare": "dare", "rps": "rock_paper_scissors", "riddle": "riddle", "riddleanswer": "riddle_answer", "guess": "guess_number", "leaderboard": "leaderboard_cmd", "dice": "dice_game", "darts": "darts_game", "basketball": "basketball_game", "bowling": "bowling_game", "football": "football_game", "slot": "slot_game", "hangman": "hangman", "hangmanguess": "hangman_guess", "tictactoe": "tictactoe", "ttt": "ttt_move", "wordchain": "wordchain_start", "chainword": "chain_word", "trivia": "trivia_category", "wordle": "wordle", "wordleguess": "wordle_guess"},
        "moderation": {"mute": "mute", "unmute": "unmute", "ban": "ban", "kick": "kick", "warn": "warn", "rules": "show_rules", "warnings": "check_warnings", "clearwarns": "clear_warnings", "pin": "pin", "unpin": "unpin", "purge": "purge", "setrules": "set_rules", "lock": "lock", "unlock": "unlock"},
        "utility": {"id": "get_id", "info": "user_info", "remind": "remind", "groupinfo": "group_info", "afk": "set_afk", "report": "report"},
        "aesthetic": {"aura": "aura_command", "identity": "identity_command", "vibecheck": "vibecheck_command", "shadow": "shadow_command", "element": "element_command", "corecode": "corecode_command", "universe": "universe_command", "ritual": "ritual_command", "duality": "duality_command", "glitch": "glitch_command", "nightreport": "nightreport_command", "sigil": "sigil_command"},
        "friendship": {"bestie": "bestie", "duo": "duo", "friendship": "friendship_score", "tagbestie": "tag_bestie", "squad": "squad", "loyalty": "loyalty", "randomship": "random_ship", "matchmaker": "matchmaker"},
        "fun": {"roast": "roast", "compliment": "compliment", "8ball": "eight_ball", "vibe": "vibe", "quote": "quote", "poll": "poll", "ratethis": "rate_this", "impostor": "impostor_start", "revealimpostor": "impostor_reveal"},
        "matchmaking": {"crush": "set_crush", "clearcrush": "clear_crush", "secretadmirer": "secret_admirer"},
        "stats": {"stats": "stats", "topactive": "top_active", "msgcount": "msg_count"},
        "events": {"joined": "show_joined", "left": "show_left", "setwelcome": "set_welcome", "setgoodbye": "set_goodbye", "invite": "get_invite"},
        "economy": {"daily": "daily", "balance": "balance", "gamble": "gamble", "richest": "economy_leaderboard"},
        "timecapsule": {"timecapsule": "timecapsule", "capsules": "list_capsules"},
        "marriage": {"marry": "marry", "accept": "accept", "divorce": "divorce", "profile": "profile", "work": "work", "chests": "chests", "shop": "shop", "buy": "buy", "inventory": "inventory", "gift": "gift", "settings": "settings"},
        "deathgames": {"deathstatus": "deathstatus", "roulette": "roulette", "deathgame": "deathgame", "joingame": "joingame", "startround": "startround", "kill": "kill", "vote": "vote", "endgame": "endgame"},
    }
    direct_commands = {
        "gif": "giphy_command", "streakcheck": "streakcheck_command", "vent": "vent_command", "oraclehour": "oraclehour_command", "enter": "enter_command", "eventcheck": "eventcheck_command", "mines": "mines_command", "bet": "bet_command", "betstats": "betstats_command", "topbet": "topbet_command", "wallet": "wallet_command", "deposit": "deposit_command", "withdraw": "withdraw_command", "setpass": "setpass_command", "changepass": "changepass_command", "recover": "recover_command", "hug": "hug_cmd", "pat": "pat_cmd", "highfive": "highfive_cmd", "slap": "slap_cmd", "kiss": "kiss_cmd", "poke": "poke_cmd", "cuddle": "cuddle_cmd", "wave": "wave_cmd", "bite": "bite_cmd", "tickle": "tickle_cmd", "fastmath": "fastmath_command", "wordbomb": "wordbomb_command", "mysterybox": "mysterybox_command", "duel": "duel_command", "confess": "confess_command", "rank": "rank_command", "muse": "muse_command", "bond": "bond_command", "signal": "signal_command", "couples": "couples_command", "bondstatus": "bondstatus_command", "verdict": "verdict_command", "hotseat": "hotseat_command", "silence": "silence_command", "cricket": "cricket_command", "call": "cricket_predict_command", "cpredict": "cricket_predict_command", "cbet": "cricket_bet_command", "cwin": "cricket_win_command", "ctournament": "cricket_tournament_command", "cpick": "cricket_pick_command", "cplay": "cricket_play_command", "broadcast": "broadcast_command", "announce": "announce_command", "startcouple": "startcouple_command", "joincouple": "joincouple_command", "couplestatus": "couplestatus_command",
    }
    _assert_no_duplicate_declarations(module_commands, direct_commands)

    added: list[str] = []
    skipped: list[str] = []
    for module_name, commands in module_commands.items():
        module = module_map[module_name]
        for command, callback_name in commands.items():
            if command in reserved or command in existing:
                continue
            if _add_command(app, existing, command, module, callback_name):
                added.append(command)
            else:
                skipped.append(command)

    compat_commands = {
        "checkin": (economy_compat, "checkin_command"),
        "cgift": (economy_compat, "cgift_command"),
        "coinboard": (economy_compat, "coinboard_command"),
        "rob": (economy_compat, "rob_command"),
        "survive": (deathgames_hardened, "survive"),
        "revive": (deathgames_hardened, "revive"),
    }
    for command, (target, callback_name) in compat_commands.items():
        if command in reserved or command in existing:
            continue
        if _add_command(app, existing, command, target, callback_name):
            added.append(command)
        else:
            skipped.append(command)

    # Legacy social/member trackers remain registered below because they feed
    # separate legacy verdict/title surfaces; do not silently remove them.
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, legacy_bot.track_members), group=13)
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, legacy_bot.track_msg_count), group=14)

    return {"added": added, "skipped": skipped, "total": len(added)}
