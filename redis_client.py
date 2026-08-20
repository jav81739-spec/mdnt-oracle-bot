import os
import redis.asyncio as aioredis
from typing import Optional

# Retrieve Redis URL from environment variables, defaulting to a local instance
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class RedisClientWrapper:
    """Async wrapper for Redis to match the methods used in engagement.py."""
    
    def __init__(self, url: str):
        self.url = url
        self.client: Optional[aioredis.Redis] = None

    async def connect(self):
        """Initialize the connection pool."""
        if not self.client:
            self.client = aioredis.from_url(
                self.url, 
                encoding="utf-8", 
                decode_responses=True
            )

    async def get(self, key: str) -> Optional[str]:
        await self.connect()
        return await self.client.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        await self.connect()
        await self.client.set(key, value, ex=ex)

    async def keys(self, pattern: str) -> list[str]:
        await self.connect()
        return await self.client.keys(pattern)

    async def close(self):
        """Close the connection."""
        if self.client:
            await self.client.close()
            self.client = None

# Global instance imported by engagement.py
redis_client = RedisClientWrapper(REDIS_URL)
