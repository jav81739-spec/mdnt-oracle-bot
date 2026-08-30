"""Live legacy command surface for the canonical Midnight Oracle runtime."""
from __future__ import annotations
import logging
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters
import legacy_bot
from handlers import chat, games, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage, deathgames
log=logging.getLogger("midnight.legacy_surface")

def _callback(target,name):
    cb=getattr(target,name,None)
    return cb if callable(cb) else None

def _add_command(app,existing,command,target,callback_name,*,group=0):
    name=command.lower().lstrip("/")
    if name in existing:return False
    cb=_callback(target,callback_name)
    if cb is None:
        log.warning("LEGACY_COMMAND_UNAVAILABLE | command=/%s | callback=%s.%s",name,getattr(target,"__name__",target),callback_name);return False
    app.add_handler(CommandHandler(name,cb),group=group);existing.add(name);return True

def register_legacy_surface(app):
    existing={str(command).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for handler in hs for command in (getattr(handler,"commands",None) or ())}
    reserved={"start","help","oracle","truth","memory","mymemory","forget","tod","wyr","nhie","scramble","unscramble","predict","predictions","house","quiet","wake"}
    module_map={"chat":chat,"games":games,"moderation":moderation,"utility":utility,"aesthetic":aesthetic,"friendship":friendship,"fun":fun,"matchmaking":matchmaking,"stats":stats,"events":events,"economy":economy,"timecapsule":timecapsule,"marriage":marriage,"deathgames":deathgames}
    module_commands={
      "chat":{"chat":"toggle_chat","persona":"set_persona"},
      "games":{"quiz":"quiz","dare":"dare","rps":"rock_paper_scissors","riddle":"riddle","riddleanswer":"riddle_answer","guess":"guess_number","leaderboard":"leaderboard_cmd","dice":"dice_game","darts":"darts_game","basketball":"basketball_game","bowling":"bowling_game","football":"football_game","slot":"slot_game","hangman":"hangman","hangmanguess":"hangman_guess","tictactoe":"tictactoe","ttt":"ttt_move","wordchain":"wordchain_start","chainword":"chain_word","trivia":"trivia_category","wordle":"wordle","wordleguess":"wordle_guess"},
      "moderation":{"mute":"mute","unmute":"unmute","ban":"ban","kick":"kick","warn":"warn","rules":"show_rules","warnings":"check_warnings","clearwarns":"clear_warnings","pin":"pin","unpin":"unpin","purge":"purge","setrules":"set_rules","lock":"lock","unlock":"unlock"},
      "utility":{"id":"get_id","info":"user_info","remind":"remind","groupinfo":"group_info","afk":"set_afk","report":"report"},
      "aesthetic":{"aura":"aura_command","identity":"identity_command","vibecheck":"vibecheck_command","shadow":"shadow_command","element":"element_command","corecode":"corecode_command","universe":"universe_command","ritual":"ritual_command","duality":"duality_command","glitch":"glitch_command","nightreport":"nightreport_command","sigil":"sigil_command"},
      "friendship":{"bestie":"bestie","duo":"duo","friendship":"friendship_score","tagbestie":"tag_bestie","squad":"squad","loyalty":"loyalty","randomship":"random_ship","matchmaker":"matchmaker","friendshiptest":"friendship_test"},
      "fun":{"roast":"roast","compliment":"compliment","8ball":"eight_ball","vibe":"vibe","quote":"quote","poll":"poll","ratethis":"rate_this","impostor":"impostor_start","revealimpostor":"impostor_reveal"},
      "matchmaking":{"crush":"set_crush","clearcrush":"clear_crush","secretadmirer":"secret_admirer"},
      "stats":{"stats":"stats","topactive":"top_active","msgcount":"msg_count"},
      "events":{"joined":"show_joined","left":"show_left","setwelcome":"set_welcome","setgoodbye":"set_goodbye","invite":"get_invite"},
      "economy":{"daily":"daily","balance":"balance","gamble":"gamble","richest":"economy_leaderboard"},
      "timecapsule":{"timecapsule":"timecapsule","capsules":"list_capsules"},
      "marriage":{"marry":"marry","accept":"accept","divorce":"divorce","profile":"profile","work":"work","chests":"chests","shop":"shop","buy":"buy","inventory":"inventory","gift":"gift","settings":"settings"},
      "deathgames":{"survive":"survive","revive":"revive","deathstatus":"deathstatus","roulette":"roulette","joingame":"joingame","startround":"startround","kill":"kill","vote":"vote","endgame":"endgame"}}
    added=[];skipped=[]
    for mn,commands in module_commands.items():
        for command,cb in commands.items():
            if command in reserved or command in existing:continue
            (_add_command(app,existing,command,module_map[mn],cb) and added.append(command)) or skipped.append(command)
    direct={"gif":"giphy_command","checkin":"checkin_command","streakcheck":"streakcheck_command","vent":"vent_command","cgift":"cgift_command","coinboard":"coinboard_command","rob":"eng_rob_command","oraclehour":"oraclehour_command","enter":"enter_command","eventcheck":"eventcheck_command","wallet":"wallet_command","deposit":"deposit_command","withdraw":"withdraw_command","hug":"hug_cmd","pat":"pat_cmd","highfive":"highfive_cmd","slap":"slap_cmd","kiss":"kiss_cmd","poke":"poke_cmd","cuddle":"cuddle_cmd","wave":"wave_cmd","bite":"bite_cmd","tickle":"tickle_cmd","fastmath":"fastmath_command","wordbomb":"wordbomb_command","mysterybox":"mysterybox_command","duel":"duel_command","confess":"confess_command","rank":"rank_command","muse":"muse_command","bond":"bond_command","signal":"signal_command","couples":"couples_command","bondstatus":"bondstatus_command","verdict":"verdict_command","hotseat":"hotseat_command","silence":"silence_command","cricket":"cricket_command","call":"cricket_predict_command","cpredict":"cricket_predict_command","cbet":"cricket_bet_command","cwin":"cricket_win_command","ctournament":"cricket_tournament_command","cpick":"cricket_pick_command","cplay":"cricket_play_command","broadcast":"broadcast_command","announce":"announce_command","deathgame":"deathgame_start"}
    for command,cb in direct.items():
        if command in reserved or command in existing:continue
        (_add_command(app,existing,command,legacy_bot,cb) and added.append(command)) or skipped.append(command)
    try:
        from telegram.ext import ChatMemberHandler
        if callable(getattr(legacy_bot,"mines_cb",None)):app.add_handler(CallbackQueryHandler(legacy_bot.mines_cb,pattern=r"^mn_"),group=0)
        if callable(getattr(legacy_bot,"fastmath_answer",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.fastmath_answer),group=9)
        if callable(getattr(legacy_bot,"wordbomb_play",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.wordbomb_play),group=10)
        if callable(getattr(legacy_bot,"silence_watcher",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.silence_watcher),group=12)
        if callable(getattr(legacy_bot,"track_groups",None)):app.add_handler(MessageHandler(filters.ChatType.GROUPS,legacy_bot.track_groups),group=15)
        if callable(getattr(legacy_bot,"track_members",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_members),group=13)
        if callable(getattr(legacy_bot,"track_msg_count",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_msg_count),group=14)
        if callable(getattr(legacy_bot,"track_group_activity",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_group_activity),group=11)
        if callable(getattr(legacy_bot,"_register_bond_activity",None)):app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND,legacy_bot._register_bond_activity),group=-10)
        if callable(getattr(legacy_bot,"midnight_member_welcome",None)):app.add_handler(ChatMemberHandler(legacy_bot.midnight_member_welcome,ChatMemberHandler.CHAT_MEMBER))
    except Exception:log.exception("LEGACY_AUXILIARY_REGISTRATION_FAILED")
    log.info("LEGACY_SURFACE_READY | added=%d | skipped=%d | total=%d",len(added),len(skipped),len(existing))
    return {"added":added,"skipped":skipped,"total":len(existing)}
