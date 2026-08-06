"""
Time Capsule — lock a message that only gets posted back to the group at
a future time you pick.

HONEST LIMITATION: this uses the bot's job_queue, which lives in memory.
If Render restarts your service (free-tier sleep, redeploy, crash) before
the capsule's unlock time, the scheduled job is lost and the message
will NOT fire. This works reliably for short delays (minutes to a few
hours) on a free instance that's being kept awake. For anything longer
than a day, there's real risk it won't survive — worth knowing before
your group relies on it for something meaningful.
"""
from telegram import Update
from telegram.ext import ContextTypes

# {chat_id: [ {"text":.., "author":.., "unlock_at": iso str} ]} — just a log for /capsules
capsule_log = {}


def _parse_duration(duration_str: str) -> int | None:
    """Parses '10m', '2h', '3d' into seconds. Returns None if invalid."""
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


async def timecapsule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /timecapsule 3d Your message here"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /timecapsule [delay] [message]\n"
            "Delay examples: 10m, 2h, 3d\n\n"
            "⚠️ Note: on free hosting, capsules longer than a day risk being "
            "lost if the server restarts before unlock time. Best for same-day capsules."
        )
        return

    delay_seconds = _parse_duration(context.args[0])
    if delay_seconds is None:
        await update.message.reply_text("Invalid delay format. Use e.g. 10m, 2h, 3d")
        return

    message_text = " ".join(context.args[1:])
    chat_id = update.effective_chat.id
    author = update.effective_user

    async def _unlock_capsule(ctx):
        await ctx.bot.send_message(
            chat_id,
            f"⏳ *A time capsule has unlocked!*\n\n"
            f"Sealed by {author.first_name}:\n\n\"{message_text}\"",
            parse_mode="Markdown",
        )

    context.job_queue.run_once(lambda ctx: _unlock_capsule(ctx), when=delay_seconds)

    capsule_log.setdefault(chat_id, [])
    capsule_log[chat_id].append({"text": message_text, "author": author.first_name, "delay": context.args[0]})

    await update.message.reply_text(
        f"🔒 Time capsule sealed! It'll unlock in {context.args[0]}.\n"
        f"_(Reminder: very long delays may not survive a server restart on free hosting)_",
        parse_mode="Markdown",
    )


async def list_capsules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    capsules = capsule_log.get(chat_id, [])
    if not capsules:
        await update.message.reply_text("No time capsules sealed yet — use /timecapsule to start one.")
        return
    lines = [f"🔒 by {c['author']}, unlocking in {c['delay']}" for c in capsules[-10:]]
    await update.message.reply_text("📦 *Sealed capsules (pending):*\n\n" + "\n".join(lines), parse_mode="Markdown")
