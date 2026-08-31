"""Live legacy command surface for the canonical Midnight Oracle runtime."""
from __future__ import annotations
import logging, os
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError
import legacy_bot
from handlers import chat, games, moderation, utility, aesthetic, friendship, fun, matchmaking, stats, events, economy, timecapsule, marriage, deathgames
log = logging.getLogger("midnight.legacy_surface")

_PROTECTED = {"broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload","shutdown","restart","admin","moderation","mute","unmute","ban","warn","clearwarns","pin","unpin","purge","setrules","lock","unlock","groupinfo","setwelcome","setgoodbye","rob","withdraw","deposit","buy","gift","kill","vote","endgame","startround","deathgame"}
_OWNER_ONLY = {"broadcast","announce","midnightmap","ownerstatus","ownerstats","setcommands","reload","shutdown","restart"}

def _callback(target, name):
    cb = getattr(target, name, None)
    return cb if callable(cb) else None

async def _is_owner(update):
    try:return int(os.getenv("OWNER_ID", "0") or "0") == int(update.effective_user.id)
    except Exception:return False

async def _is_group_admin(update, context):
    if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):return False
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ("administrator", "creator")
    except (TelegramError, AttributeError, TypeError):return False

async def _authorized(update, context, command):
    if command in _OWNER_ONLY:return await _is_owner(update)
    return await _is_owner(update) or await _is_group_admin(update, context)

def _protected_callback(cb, command):
    if command not in _PROTECTED:return cb
    async def guarded(update, context):
        if not await _authorized(update, context, command):
            if getattr(update, "effective_message", None):await update.effective_message.reply_text("☾ This command is restricted to the owner or group admins.",reply_to_message_id=update.effective_message.message_id)
            return
        return await cb(update, context)
    guarded.__name__ = getattr(cb, "__name__", f"guarded_{command}")
    return guarded

def _add_command(app, existing, command, target, callback_name, *, group=0):
    name = command.lower().lstrip("/")
    if name in existing:return False
    cb = _callback(target, callback_name)
    if cb is None:raise RuntimeError(f"COMMAND_CALLBACK_MISSING: /{name} -> {getattr(target, '__name__', target)}.{callback_name}")
    app.add_handler(CommandHandler(name, _protected_callback(cb, name)), group=group);existing.add(name);return True

def _assert_no_duplicate_declarations(module_commands, direct):
    owners={}
    for module, commands in module_commands.items():
        for command, callback_name in commands.items():
            previous=owners.get(command)
            if previous is None:owners[command]=(module,callback_name);continue
            previous_module,previous_callback=previous;raise RuntimeError(f"COMMAND_OWNER_COLLISION: /{command}: {previous_module}.{previous_callback} vs {module}.{callback_name}")
    for command, callback_name in direct.items():
        previous=owners.get(command)
        if previous is None:continue
        previous_module,previous_callback=previous;raise RuntimeError(f"COMMAND_OWNER_COLLISION: /{command}: {previous_module}.{previous_callback} vs legacy_bot.{callback_name}")

def register_legacy_surface(app):
    existing={str(command).lower().lstrip("/") for hs in getattr(app,"handlers",{}).values() for handler in hs for command in (getattr(handler,"commands",None) or ())}
    reserved={"start","help","oracle","truth","memory","mymemory","forget","tod","wyr","nhie","scramble","unscramble","predict","predictions","house","quiet","wake"}
    module_map={"chat":chat,"games":games,"moderation":moderation,"utility":utility,"aesthetic":aesthetic,"friendship":friendship,"fun":fun,"matchmaking":matchmaking,"stats":stats,"events":events,"economy":economy,"timecapsule":timecapsule,"marriage":marriage,"deathgames":deathgames}
    module_commands={"chat":{"chat":"toggle_chat","persona":"set_persona"},"games":{"quiz":"quiz","dare":"dare","rps":"rock_paper_scissors","riddle":"riddle","riddleanswer":"riddle_answer","guess":"guess_number","leaderboard":"leaderboard_cmd","dice":"dice_game","darts":"darts_game","basketball":"basketball_game","bowling":"bowling_game","football":"football_game","slot":"slot_game","hangman":"hangman","hangmanguess":"hangman_guess","tictactoe":"tictactoe","ttt":"ttt_move","wordchain":"wordchain_start","chainword":"chain_word","trivia":"trivia_category","wordle":"wordle","wordleguess":"wordle_guess"},"moderation":{"mute":"mute","unmute":"unmute","ban":"ban","warn":"warn","rules":"show_rules","warnings":"check_warnings","clearwarns":"clear_warnings","pin":"pin","unpin":"unpin","purge":"purge","setrules":"set_rules","lock":"lock","unlock":"unlock"},"utility":{"id":"get_id","info":"user_info","remind":"remind","groupinfo":"group_info","afk":"set_afk","report":"report"},"aesthetic":{"aura":"aura_command","identity":"identity_command","vibecheck":"vibecheck_command","shadow":"shadow_command","element":"element_command","corecode":"corecode_command","universe":"universe_command","ritual":"ritual_command","duality":"duality_command","glitch":"glitch_command","nightreport":"nightreport_command","sigil":"sigil_command"},"friendship":{"hug":"hug","kiss":"kiss","pat":"pat","kick":"kick","slap":"slap","punch":"punch","highfive":"highfive","cuddle":"cuddle","poke":"poke","bonk":"bonk","bite":"bite","wave":"wave","wink":"wink","dance":"dance","roast":"roast","cheer":"cheer","comfort":"comfort","tickle":"tickle","salute":"salute","stare":"stare","handshake":"handshake","fistbump":"fistbump","shoulderpat":"shoulderpat","cheers":"cheers","bestie":"bestie","duo":"duo","friendship":"friendship_score","tagbestie":"tag_bestie","squad":"squad","loyalty":"loyalty","randomship":"random_ship","matchmaker":"matchmaker","friendshiptest":"friendship_test","ship":"ship"},"fun":{"compliment":"compliment","8ball":"eight_ball","vibe":"vibe","quote":"quote","poll":"poll","ratethis":"rate_this","impostor":"impostor_start","revealimpostor":"impostor_reveal"},"matchmaking":{"crush":"set_crush","clearcrush":"clear_crush","secretadmirer":"secret_admirer"},"stats":{"stats":"stats","topactive":"top_active","msgcount":"msg_count"},"events":{"joined":"show_joined","left":"show_left","setwelcome":"set_welcome","setgoodbye":"set_goodbye","invite":"get_invite"},"economy":{"daily":"daily","balance":"balance","gamble":"gamble","richest":"economy_leaderboard"},"timecapsule":{"timecapsule":"timecapsule","capsules":"list_capsules"},"marriage":{"marry":"marry","accept":"accept","divorce":"divorce","profile":"profile","work":"work","chests":"chests","shop":"shop","buy":"buy","inventory":"inventory","gift":"gift","settings":"settings"},"deathgames":{"survive":"survive","revive":"revive","deathstatus":"deathstatus","roulette":"roulette","joingame":"joingame","startround":"startround","kill":"kill","vote":"vote","endgame":"endgame"}}
    direct={"gif":"send_random_gif","image":"image_command","checkin":"checkin_command","streakcheck":"streakcheck_command","vent":"vent_command","cgift":"cgift_command","coinboard":"coinboard_command","rob":"eng_rob_command","oraclehour":"oraclehour_command","enter":"enter_command","eventcheck":"eventcheck_command","wallet":"wallet_command","deposit":"deposit_command","withdraw":"withdraw_command","fastmath":"fastmath_command","wordbomb":"wordbomb_command","mysterybox":"mysterybox_command","duel":"duel_command","confess":"confess_command","rank":"rank_command","muse":"muse_command","bond":"bond_command","signal":"signal_command","signalcheck":"signal_command","couples":"couples_command","bondstatus":"bondstatus_command","verdict":"verdict_command","hotseat":"hotseat_command","silence":"silence_command","cricket":"cricket_command","call":"cricket_predict_command","cpredict":"cricket_predict_command","cbet":"cricket_bet_command","cwin":"cricket_win_command","ctournament":"cricket_tournament_command","cpick":"cricket_pick_command","cplay":"cricket_play_command","broadcast":"broadcast_command","announce":"announce_command","deathgame":"deathgame_start"}
    _assert_no_duplicate_declarations(module_commands,direct)
    added=[]
    for mn,commands in module_commands.items():
        for command,cb in commands.items():
            if command in reserved or command in existing:continue
            if _add_command(app,existing,command,module_map[mn],cb):added.append(command)
    for command,cb in direct.items():
        if command in reserved or command in existing:continue
        if _add_command(app,existing,command,chat if command in {"gif","image"} else legacy_bot,cb):added.append(command)
    try:
        if callable(getattr(legacy_bot,"mines_cb",None)):app.add_handler(CallbackQueryHandler(legacy_bot.mines_cb,pattern=r"^mn_"))
        if callable(getattr(legacy_bot,"fastmath_answer",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.fastmath_answer),group=9)
        if callable(getattr(legacy_bot,"wordbomb_play",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.wordbomb_play),group=10)
        if callable(getattr(legacy_bot,"silence_watcher",None)):app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,legacy_bot.silence_watcher),group=12)
        if callable(getattr(legacy_bot,"track_groups",None)):app.add_handler(MessageHandler(filters.ChatType.GROUPS,legacy_bot.track_groups),group=15)
        if callable(getattr(legacy_bot,"track_members",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_members),group=13)
        if callable(getattr(legacy_bot,"track_msg_count",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_msg_count),group=14)
        if callable(getattr(legacy_bot,"track_group_activity",None)):app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS,legacy_bot.track_group_activity),group=11)
        if callable(getattr(legacy_bot,"_register_bond_activity",None)):app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND,legacy_bot._register_bond_activity),group=-10)
        if callable(getattr(legacy_bot,"midnight_member_welcome",None)):
            ChatMemberHandler=__import__("telegram.ext",fromlist=["ChatMemberHandler"]).ChatMemberHandler
            app.add_handler(ChatMemberHandler(legacy_bot.midnight_member_welcome,ChatMemberHandler.CHAT_MEMBER))
    except Exception:log.exception("LEGACY_AUXILIARY_REGISTRATION_FAILED")
    log.info("LEGACY_SURFACE_READY | added=%d | total=%d",len(added),len(existing))
    return {"added":added,"total":len(existing)}
