"""
Time Capsule — lock a message that only gets posted back to the group at
a future time you pick.

NOW PERSISTED: capsules are saved to Redis (via handlers/storage.py) with
an absolute unlock timestamp. On bot startup, load_and_reschedule() reads
all pending capsules and re-schedules whatever time is left — so even if
Render restarts your bot mid-wait, the capsule still fires when it
should (as long as UPSTASH_REDIS_REST_URL / TOKEN are set).

Without those env vars set, this still works for same-session capsules,
it just won't survive a restart — same as before.
"""
import datetime
from telegram import Update
from telegram.ext import ContextTypes, Application
from handlers import storage

STORAGE_KEY = "timecapsules"

# In-memory cache: {"<chat_id>": [ {"text":, "author":, "unlock_at": iso str, "id": str}, ... ]}
capsules = {}


def _parse_duration(duration_str: str):
    if len(duration_str) < 2:
        return None
    unit = duration_str[-1].lower()
    try:
        amount = int(duration_str[:-1])
    except ValueError:
        return None
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    if unit not in multipliers:
        return None
    return amount * multipliers[unit]


async def _persist():
    await storage.save(STORAGE_KEY, capsules)


async def _fire_capsule(context: ContextTypes.DEFAULT_TYPE, chat_id: str, capsule: dict):
    await context.bot.send_message(
        int(chat_id),
        f"⏳ *A time capsule has unlocked!*\n\n"
        f"Sealed by {capsule['author']}:\n\n\"{capsule['text']}\"",
        parse_mode="Markdown",
    )
    # Remove it from the store once delivered
    if chat_id in capsules:
        capsules[chat_id] = [c for c in capsules[chat_id] if c["id"] != capsule["id"]]
        await _persist()


async def timecapsule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /timecapsule 3d Your message here"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /timecapsule [delay] [message]\n"
            "Delay examples: 10m, 2h, 3d\n\n"
            "✅ Now persisted — survives bot restarts as long as the free "
            "database is connected (see README)."
        )
        return

    delay_seconds = _parse_duration(context.args[0])
    if delay_seconds is None:
        await update.message.reply_text("Invalid delay format. Use e.g. 10m, 2h, 3d")
        return

    message_text = " ".join(context.args[1:])
    chat_id = str(update.effective_chat.id)
    author = update.effective_user

    unlock_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay_seconds)
    capsule_id = f"{author.id}-{int(unlock_at.timestamp())}"
    capsule = {
        "id": capsule_id,
        "text": message_text,
        "author": author.first_name,
        "unlock_at": unlock_at.isoformat(),
    }

    capsules.setdefault(chat_id, [])
    capsules[chat_id].append(capsule)
    await _persist()

    context.job_queue.run_once(
        lambda ctx: _fire_capsule(ctx, chat_id, capsule), when=delay_seconds
    )

    await update.message.reply_text(
        f"🔒 Time capsule sealed! It'll unlock in {context.args[0]}.\n"
        f"_(Now saved persistently — will still fire even if the bot restarts)_",
        parse_mode="Markdown",
    )


async def list_capsules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    pending = capsules.get(chat_id, [])
    if not pending:
        await update.message.reply_text("No time capsules sealed yet — use /timecapsule to start one.")
        return
    lines = [f"🔒 by {c['author']}, unlocking at {c['unlock_at'][:16].replace('T', ' ')} UTC" for c in pending]
    await update.message.reply_text("📦 *Sealed capsules (pending):*\n\n" + "\n".join(lines), parse_mode="Markdown")


async def load_and_reschedule(app: Application):
    """Call this once at bot startup (from post_init) to resume any
    capsules that were pending when the bot last shut down."""
    global capsules
    capsules = await storage.load(STORAGE_KEY, {})
    now = datetime.datetime.now(datetime.timezone.utc)
    resumed = 0
    expired = 0

    for chat_id, chat_capsules in list(capsules.items()):
        for capsule in list(chat_capsules):
            unlock_at = datetime.datetime.fromisoformat(capsule["unlock_at"])
            remaining = (unlock_at - now).total_seconds()

            if remaining <= 0:
                # Bot was offline past the unlock time — deliver it late,
                # rather than losing it silently.
                app.job_queue.run_once(
                    lambda ctx, cid=chat_id, cap=capsule: _fire_capsule(ctx, cid, cap), when=1
                )
                expired += 1
            else:
                app.job_queue.run_once(
                    lambda ctx, cid=chat_id, cap=capsule: _fire_capsule(ctx, cid, cap), when=remaining
                )
                resumed += 1

    if resumed or expired:
        import logging
        logging.getLogger(__name__).info(
            f"Time capsules: resumed {resumed}, delivered {expired} that were overdue."
        )
