"""Explicit V2 Death Games handler registration."""
from telegram.ext import CommandHandler
from handlers import deathgames_v2


def install(application) -> None:
    application.add_handler(
        CommandHandler(
            ["deathgame", "deathgames", "joingame", "startround", "kill", "vote", "endgame",
             "survive", "revive", "deathstatus", "roulette"],
            _router,
        ),
        group=15,
    )


async def _router(update, context):
    command = (update.effective_message.text or "").split()[0].split("@", 1)[0].lstrip("/").lower()
    handlers = {
        "deathgame": deathgames_v2.deathgame, "deathgames": deathgames_v2.deathgame,
        "joingame": deathgames_v2.joingame, "startround": deathgames_v2.startround,
        "kill": deathgames_v2.kill, "vote": deathgames_v2.vote, "endgame": deathgames_v2.endgame,
        "survive": deathgames_v2.survive, "revive": deathgames_v2.revive,
        "deathstatus": deathgames_v2.deathstatus, "roulette": deathgames_v2.roulette,
    }
    handler = handlers.get(command)
    if handler:
        await handler(update, context)
