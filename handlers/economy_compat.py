"""Compatibility command surface backed by the canonical economy service.

These historical command names intentionally remain available, but they no longer
read or write the legacy ``coins:<uid>`` store.  Every mutation goes through the
same scoped economy primitives used by the canonical economy commands.
"""
from __future__ import annotations

from datetime import date

from core.economy import EconomyError, service as economy


def _amount(context) -> int:
    if not context.args:
        raise ValueError("amount required")
    amount = int(context.args[0])
    if amount <= 0:
        raise ValueError("amount must be positive")
    return amount


async def checkin_command(update, context):
    # /daily is the canonical idempotent daily claim; preserve /checkin as an alias.
    from handlers.economy import daily
    return await daily(update, context)


async def coinboard_command(update, context):
    from handlers.economy import economy_leaderboard
    return await economy_leaderboard(update, context)


async def rob_command(update, context):
    from handlers.economy import rob
    return await rob(update, context)


async def cgift_command(update, context):
    message = update.message
    target = message.reply_to_message.from_user if message and message.reply_to_message else None
    if target is None:
        await message.reply_text("Reply to someone with /cgift <amount>.")
        return
    try:
        amount = _amount(context)
        _, tx = await economy.transfer(
            update.effective_user.id,
            target.id,
            amount,
            "cgift",
            scope=str(update.effective_chat.id),
        )
    except ValueError:
        await message.reply_text("Usage: /cgift <amount> (reply to the recipient).")
        return
    except EconomyError as exc:
        await message.reply_text(f"⏳ Gift failed safely: {exc}")
        return
    await message.reply_text(f"🎁 Sent {amount} coins to {target.first_name}. Their balance is now {tx.balance}.")
