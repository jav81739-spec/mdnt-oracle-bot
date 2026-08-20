"""
main.py — Midnight Oracle Bot (FULL UPDATED VERSION)
All systems integrated:
  ✅ Channel post auto-reply (channel_oracle.py)
  ✅ Daily check-in + streaks (engagement.py)
  ✅ Gift / Rob / Leaderboard / Vent (engagement.py)
  ✅ Aesthetic commands — aura, identity, oracle, shadow, etc. (aesthetic.py)
  ✅ Oracle's Hour group events (oracle_events.py)
  ✅ All original commands preserved
  ✅ Marriage system (marriage.py)
  ✅ Death Games (deathgames.py)
  ✅ Gemini AI chat
  ✅ GIPHY reactions
  ✅ Time capsules
  ✅ Moderation
  ✅ Economy
  ✅ Matchmaking

COMMANDS CUT (merged or replaced):
  ❌ /prophecy → merged into /oracle
  ❌ /omen     → merged into /oracle
  ❌ /vibe     → merged into /vibecheck
  ❌ /energy   → merged into /vibecheck
  ❌ /aesthetic → merged into /vibecheck
  ❌ /moodboard → merged into /nightreport
  ❌ /hex      → merged into /curse
  ❌ /whisper  → merged into /confess
"""

import os
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ─── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Environment ───────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))  # Add to Render env vars

# ─── Import all handlers ───────────────────────────────────────────────────

# NEW: Channel Oracle (auto-reply to channel posts)
from channel_oracle import get_channel_oracle_handler

# NEW: Engagement system
from engagement import (
    checkin_command,
    gift_command,
    rob_command,
    leaderboard_command,
    vent_command,
    streakcheck_command,
)

# NEW: Aesthetic commands
from aesthetic import (
    aura_command,
    identity_command,
    oracle_command,
    vibecheck_command,
    shadow_command,
    element_command,
    corecode_command,
    universe_command,
    ritual_command,
    duality_command,
    glitch_command,
    nightreport_command,
    sigil_command,
)

# NEW: Oracle events
from oracle_events import (
    oraclehour_command,
    enter_command,
    eventcheck_command,
    register_event_jobs,
)

# ─── EXISTING handlers (keep all your originals below) ─────────────────────
# Replace these imports with your actual existing module imports
# Examples shown — adjust to match your file structure:

from commands.general import (
    start_command,
    help_command,
    ping_command,
)

from commands.games import (
    rps_command,
    trivia_command,
    guess_command,
    wordchain_command,
    quiz_command,
    truth_command,
    dare_command,
    wouldyourather_command,
    neverhaveiever_command,
)

from commands.economy import (
    coins_command,
    daily_command,
    work_command,
    shop_command,
    buy_command,
    inventory_command,
    transfer_command,
    slots_command,
    flip_command,
    dice_command,
)

from commands.social import (
    hug_command,
    slap_command,
    kiss_command,
    pat_command,
    poke_command,
    bite_command,
    cuddle_command,
    highfive_command,
    ship_command,
    compatibility_command,
)

from commands.mystery import (
    tarot_command,
    horoscope_command,
    curse_command,
    confess_command,
    nightmare_command,
    astral_command,
    void_command,
)

from commands.moderation import (
    ban_command,
    kick_command,
    mute_command,
    unmute_command,
    warn_command,
    warnings_command,
    purge_command,
    pin_command,
)

from commands.stats import (
    stats_command,
    rank_command,
    profile_command,
    activity_command,
)

from commands.matchmaking import (
    matchme_command,
    icebreaker_command,
    findfriend_command,
)

from commands.capsule import (
    capsule_command,
    opencapsule_command,
    mycapsules_command,
)

from marriage import (
    marry_command,
    marry_accept_callback,
    divorce_command,
    mywife_command,
    marriagestatus_command,
    topmarriages_command,
)

from deathgames import (
    startgame_command,
    joingame_command,
    begingame_command,
    vote_command,
    gamestatus_command,
    endgame_command,
    deathgame_callback,
)

from ai_chat import handle_ai_message  # your existing Gemini chat handler
from sticker_gif import handle_sticker_gif  # your existing GIF/sticker handler


# ─── Build & register ──────────────────────────────────────────────────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Channel Oracle (MUST be first or high priority) ──────────────────
    app.add_handler(get_channel_oracle_handler(), group=0)

    # ── General ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))

    # ── NEW: Engagement ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("gift", gift_command))
    app.add_handler(CommandHandler("rob", rob_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("vent", vent_command))
    app.add_handler(CommandHandler("streakcheck", streakcheck_command))

    # ── NEW: Oracle Events ────────────────────────────────────────────────
    app.add_handler(CommandHandler("oraclehour", oraclehour_command))
    app.add_handler(CommandHandler("enter", enter_command))
    app.add_handler(CommandHandler("eventcheck", eventcheck_command))

    # ── NEW: Aesthetic (replaces old duplicates) ──────────────────────────
    app.add_handler(CommandHandler("aura", aura_command))
    app.add_handler(CommandHandler("identity", identity_command))
    app.add_handler(CommandHandler("oracle", oracle_command))        # replaces /prophecy + /omen
    app.add_handler(CommandHandler("vibecheck", vibecheck_command))  # replaces /vibe + /energy
    app.add_handler(CommandHandler("shadow", shadow_command))
    app.add_handler(CommandHandler("element", element_command))
    app.add_handler(CommandHandler("corecode", corecode_command))
    app.add_handler(CommandHandler("universe", universe_command))
    app.add_handler(CommandHandler("ritual", ritual_command))
    app.add_handler(CommandHandler("duality", duality_command))
    app.add_handler(CommandHandler("glitch", glitch_command))
    app.add_handler(CommandHandler("nightreport", nightreport_command))
    app.add_handler(CommandHandler("sigil", sigil_command))

    # ── Games ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("rps", rps_command))
    app.add_handler(CommandHandler("trivia", trivia_command))
    app.add_handler(CommandHandler("guess", guess_command))
    app.add_handler(CommandHandler("wordchain", wordchain_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("truth", truth_command))
    app.add_handler(CommandHandler("dare", dare_command))
    app.add_handler(CommandHandler("wouldyourather", wouldyourather_command))
    app.add_handler(CommandHandler("neverhaveiever", neverhaveiever_command))

    # ── Economy ───────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("coins", coins_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("work", work_command))
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("inventory", inventory_command))
    app.add_handler(CommandHandler("transfer", transfer_command))
    app.add_handler(CommandHandler("slots", slots_command))
    app.add_handler(CommandHandler("flip", flip_command))
    app.add_handler(CommandHandler("dice", dice_command))

    # ── Social / Actions ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("hug", hug_command))
    app.add_handler(CommandHandler("slap", slap_command))
    app.add_handler(CommandHandler("kiss", kiss_command))
    app.add_handler(CommandHandler("pat", pat_command))
    app.add_handler(CommandHandler("poke", poke_command))
    app.add_handler(CommandHandler("bite", bite_command))
    app.add_handler(CommandHandler("cuddle", cuddle_command))
    app.add_handler(CommandHandler("highfive", highfive_command))
    app.add_handler(CommandHandler("ship", ship_command))
    app.add_handler(CommandHandler("compatibility", compatibility_command))

    # ── Mystery / Aesthetic ───────────────────────────────────────────────
    app.add_handler(CommandHandler("tarot", tarot_command))
    app.add_handler(CommandHandler("horoscope", horoscope_command))
    app.add_handler(CommandHandler("curse", curse_command))
    app.add_handler(CommandHandler("confess", confess_command))
    app.add_handler(CommandHandler("nightmare", nightmare_command))
    app.add_handler(CommandHandler("astral", astral_command))
    app.add_handler(CommandHandler("void", void_command))

    # ── Moderation ────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("warnings", warnings_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("pin", pin_command))

    # ── Stats ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("rank", rank_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("activity", activity_command))

    # ── Matchmaking ───────────────────────────────────────────────────────
    app.add_handler(CommandHandler("matchme", matchme_command))
    app.add_handler(CommandHandler("icebreaker", icebreaker_command))
    app.add_handler(CommandHandler("findfriend", findfriend_command))

    # ── Time Capsules ─────────────────────────────────────────────────────
    app.add_handler(CommandHandler("capsule", capsule_command))
    app.add_handler(CommandHandler("opencapsule", opencapsule_command))
    app.add_handler(CommandHandler("mycapsules", mycapsules_command))

    # ── Marriage ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("marry", marry_command))
    app.add_handler(CommandHandler("divorce", divorce_command))
    app.add_handler(CommandHandler("mywife", mywife_command))
    app.add_handler(CommandHandler("marriagestatus", marriagestatus_command))
    app.add_handler(CommandHandler("topmarriages", topmarriages_command))
    app.add_handler(CallbackQueryHandler(marry_accept_callback, pattern="^marry_"))

    # ── Death Games ───────────────────────────────────────────────────────
    app.add_handler(CommandHandler("startgame", startgame_command))
    app.add_handler(CommandHandler("joingame", joingame_command))
    app.add_handler(CommandHandler("begingame", begingame_command))
    app.add_handler(CommandHandler("vote", vote_command))
    app.add_handler(CommandHandler("gamestatus", gamestatus_command))
    app.add_handler(CommandHandler("endgame", endgame_command))
    app.add_handler(CallbackQueryHandler(deathgame_callback, pattern="^dg_"))

    # ── AI Chat + GIF reactions (catch-all, lowest priority) ──────────────
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.IS_AUTOMATIC_FORWARD,
            handle_ai_message
        ),
        group=1
    )
    app.add_handler(
        MessageHandler(
            (filters.Sticker.ALL | filters.Document.IMAGE),
            handle_sticker_gif
        ),
        group=2
    )

    # ── Register scheduled jobs ───────────────────────────────────────────
    if GROUP_CHAT_ID:
        register_event_jobs(app, GROUP_CHAT_ID)
    else:
        logger.warning("GROUP_CHAT_ID not set — weekly summary and auto-events disabled")

    return app


# ─── Entry point ───────────────────────────────────────────────────────────
def main():
    app = build_app()
    logger.info("🌙 Midnight Oracle is awakening...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
