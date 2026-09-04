"""Non-fatal structured error visibility for autonomous components."""
from __future__ import annotations
import logging
import time

log = logging.getLogger("midnight.alert")


async def soft_alert(storage_client, label: str, error: Exception) -> None:
    """Record an error marker when possible without changing control flow."""
    if storage_client:
        key = f"error:{label}:{int(time.time())}"
        try:
            saved = await storage_client.setex(key, 3600, str(error)[:1000])
            if saved is False:
                log.warning("SOFT_ALERT_STORAGE_REJECTED | label=%s", label)
        except Exception:
            log.exception("SOFT_ALERT_STORAGE_FAILED | label=%s", label)
    log.error("SOFT_ALERT | %s | %r", label, error)
