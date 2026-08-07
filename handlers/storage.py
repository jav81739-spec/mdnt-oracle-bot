"""
Persistent storage using Upstash Redis's free REST API.

WHY THIS EXISTS: Render's free tier wipes the entire filesystem on every
restart, redeploy, or sleep/wake cycle — a local SQLite file would NOT
survive that. Upstash's free tier is a real external database, so data
saved here survives even if your Render service restarts completely.

If UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN aren't set, these
functions silently no-op (save does nothing, load returns the default)
so the bot still runs fine locally — it just won't persist until you
add those two environment variables.
"""
import os
import json
import httpx

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")


def is_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


async def save(key: str, value) -> None:
    if not is_configured():
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            content=json.dumps(value),
        )


async def load(key: str, default=None):
    if not is_configured():
        return default
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{UPSTASH_URL}/get/{key}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"})
        data = resp.json()
        result = data.get("result")
        if result is None:
            return default
        return json.loads(result)
