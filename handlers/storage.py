"""
Persistent storage using Upstash Redis's free REST API.

WHY THIS EXISTS: Render's free tier wipes the entire filesystem on every
restart, redeploy, or sleep/wake cycle — a local SQLite file would NOT survive that.
Upstash's free tier is a real external database, so data saved here survives even if
your Render service restarts completely.

If UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN aren't set, these functions
silently no-op (save does nothing, load returns the default) so the bot still runs
fine locally — it just won't persist until you add those two environment variables.
"""

import os
import json
import urllib.parse
from typing import Any, Optional

import httpx

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")


def is_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


def _key_path(key: str) -> str:
    return urllib.parse.quote(key, safe="")


async def save(key: str, value: Any) -> None:
    if not is_configured():
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{UPSTASH_URL}/set/{_key_path(key)}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
                content=json.dumps(value),
            )
    except Exception:
        return


async def load(key: str, default: Any = None) -> Any:
    if not is_configured():
        return default

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{UPSTASH_URL}/get/{_key_path(key)}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result")
        if result is None:
            return default

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result

    except Exception:
        return default


async def delete(key: str) -> None:
    if not is_configured():
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{UPSTASH_URL}/del/{_key_path(key)}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
    except Exception:
        return


async def exists(key: str) -> bool:
    if not is_configured():
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{UPSTASH_URL}/exists/{_key_path(key)}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return bool(data.get("result", 0))
    except Exception:
        return False
