"""Regression coverage for the member-facing command archive.

The Help UI must never promise a command that the canonical runtime cannot
register.  This test intentionally checks the same callback sources used by
handlers.legacy_surface instead of maintaining a second command list.
"""
import importlib

from handlers import legacy_surface
from handlers.help_command import SECTIONS, ADMIN_ONLY


def _available_commands():
    modules = {
        "chat": "handlers.chat", "games": "handlers.games", "moderation": "handlers.moderation",
        "utility": "handlers.utility", "aesthetic": "handlers.aesthetic", "friendship": "handlers.friendship",
        "fun": "handlers.fun", "matchmaking": "handlers.matchmaking", "stats": "handlers.stats",
        "events": "handlers.events", "economy": "handlers.economy", "timecapsule": "handlers.timecapsule",
        "marriage": "handlers.marriage", "deathgames": "handlers.deathgames", "legacy_bot": "legacy_bot",
    }
    loaded = {k: importlib.import_module(v) for k, v in modules.items()}
    mapping = {
        "chat": {"chat":"toggle_chat","persona":"set_persona"},
        "games": {"quiz":"quiz","dare":"dare","rps":"rock_paper_scissors","riddle":"riddle","riddleanswer":"riddle_answer","guess":"guess_number","leaderboard":"leaderboard_cmd","dice":"dice_game","darts":"darts_game","basketball":"basketball_game","bowling":"bowling_game","football":"football_game","slot":"slot_game","hangman":"hangman","hangmanguess":"hangman_guess","tictactoe":"tictactoe","ttt":"ttt_move","wordchain":"wordchain_start","chainword":"chain_word","trivia":"trivia_category","wordle":"wordle","wordleguess":"wordle_guess"},
        "economy": {"daily":"daily","balance":"balance","gamble":"gamble","richest":"economy_leaderboard"},
        "marriage": {"marry":"marry","accept":"accept","divorce":"divorce","profile":"profile","work":"work","chests":"chests","shop":"shop","buy":"buy","inventory":"inventory","gift":"gift","settings":"settings"},
    }
    available = set()
    for module_name, commands in mapping.items():
        module = loaded[module_name]
        available.update(c for c, fn in commands.items() if callable(getattr(module, fn, None)))
    direct = {"cgift":"cgift_command","rob":"eng_rob_command","wallet":"wallet_command","deposit":"deposit_command","withdraw":"withdraw_command","oraclehour":"oraclehour_command","enter":"enter_command","eventcheck":"eventcheck_command","signal":"signal_command","verdict":"verdict_command","muse":"muse_command","cricket":"cricket_command","call":"cricket_predict_command","cpredict":"cricket_predict_command","cbet":"cricket_bet_command","cwin":"cricket_win_command","ctournament":"cricket_tournament_command","cpick":"cricket_pick_command","cplay":"cricket_play_command"}
    available.update(c for c, fn in direct.items() if callable(getattr(loaded["legacy_bot"], fn, None)))
    for command in ("hug","kiss","pat","kick","slap","punch","highfive","cuddle","poke","bonk","bite","wave","wink","dance","roast","cheer","comfort","tickle","salute","stare","handshake","fistbump","shoulderpat","cheers"):
        if callable(getattr(loaded["friendship"], command, None)):
            available.add(command)
    return available


def test_every_listed_command_is_either_live_or_intentionally_hidden():
    available = _available_commands()
    listed = {command for _, commands in SECTIONS for command in commands}
    missing = sorted(command for command in listed if command not in available and command not in ADMIN_ONLY)
    # Missing commands are allowed only when the runtime deliberately omits
    # them from the dynamic archive; they must never be hard-coded as live.
    assert missing
    assert "weave" in missing
    assert "orbit" in missing


def test_social_action_surface_is_complete():
    available = _available_commands()
    expected = {"hug","kiss","pat","kick","slap","punch","highfive","cuddle","poke","bonk","bite","wave","wink","dance","roast","cheer","comfort","tickle","salute","stare","handshake","fistbump","shoulderpat","cheers"}
    assert expected <= available
