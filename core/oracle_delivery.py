"""Canonical delivery bridge for Oracle-generated experiences."""
from __future__ import annotations

from typing import Any

from telegram.error import BadRequest
from midnight_oracle.utils.logger import get_logger

log = get_logger("midnight.oracle_delivery")
BLOCK_EXPIRES_AT = 4102444800.0


async def deliver(application: Any, chat_id: int, text: str) -> bool:
    """Use the existing Social Engine posting path and quarantine permission-blocked chats."""
    from handlers.social_engine import _post

    db = application.bot_data.get("oracle_db")
    try:
        member = await application.bot.get_chat_member(chat_id, application.bot.id)
        status = str(getattr(member, "status", "")).lower()
        can_send = getattr(member, "can_send_messages", None)

        permission_blocked = status in {"left", "kicked", "banned"}
        if status == "restricted" and can_send is False:
            permission_blocked = True
        if status in {"member", "restricted"} and can_send is None:
            chat = await application.bot.get_chat(chat_id)
            permissions = getattr(chat, "permissions", None)
            if permissions is not None and getattr(permissions, "can_send_messages", True) is False:
                permission_blocked = True

        if permission_blocked:
            if db:
                await db.set_cooldown("group", str(chat_id), "delivery_blocked", BLOCK_EXPIRES_AT)
            log.info(
                "ORACLE_DELIVERY_BLOCKED | chat=%s | reason=insufficient_send_rights",
                chat_id,
            )
            return False

        await _post(application.bot, chat_id, text)
        if db:
            await db.execute(
                "DELETE FROM cooldowns WHERE scope=? AND scope_id=? AND cooldown_type=?",
                ("group", str(chat_id), "delivery_blocked"),
            )
        return True
    except BadRequest as exc:
        message = str(exc).lower()
        if "not enough rights to send" in message or "not enough rights" in message:
            if db:
                await db.set_cooldown("group", str(chat_id), "delivery_blocked", BLOCK_EXPIRES_AT)
            log.info(
                "ORACLE_DELIVERY_BLOCKED | chat=%s | reason=insufficient_send_rights",
                chat_id,
            )
        else:
            log.warning("ORACLE_DELIVERY_FAILED | chat=%s | error=%s", chat_id, exc)
        return False
    except Exception as exc:
        log.warning("ORACLE_DELIVERY_FAILED | chat=%s | error=%s", chat_id, exc)
        return False
