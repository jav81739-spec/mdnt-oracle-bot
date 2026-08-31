"""Non-fatal structured error visibility for autonomous components."""
from __future__ import annotations
import logging
import time

log = logging.getLogger("midnight.alert")

async def soft_alert(storage_client, label: str, error: Exception) -> None:
    """Store a short-lived error marker without ever changing control flow."""
    try:
        if storage_client:
            key = f"error:{label}:{int(time.time())}"
            await storage_client.setex(key, 3600, str(error)[:1000])
    except Exception:
        pass
    log.error("SOFT_ALERT | %s | %r", label, error)
