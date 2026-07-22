import json
import logging
from typing import AsyncIterator
 
import redis.asyncio as aioredis
 
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
_CHANNEL_PREFIX = "stream"
_PRESENCE_PREFIX = "presence"
_PRESENCE_TTL_SECONDS = 90

class RedisPubSubManager:
    """Manages Redis pub/sub for cross-worker WebSocket token streaming.
 
    Uses Redis db=1, completely isolated from auth token storage on db=0.
 
    Publisher and subscriber use separate Redis connections — a connection
    that has entered subscribe mode cannot issue regular commands.
    """

    def __init__(self) -> None:
        self._publisher: aioredis.Redis | None = None
        self._subscriber: aioredis.Redis | None = None
    
    async def startup(self) -> None:
        self._publisher = aioredis.from_url(
            settings.redis_url,
            db=settings.redis_db_pubsub,
            password=settings.redis_password,
            decode_responses=True,
        )
        self._subscriber = aioredis.from_url(
            settings.redis_url,
            db=settings.redis_db_pubsub,
            password=settings.redis_password,
            decode_responses=True,
        )
        logger.info("RedisPubSubManager started on db=%d", settings.redis_db_pubsub)

    async def shutdown(self) -> None:
        if self._publisher:
            await self._publisher.aclose()
        if self._subscriber:
            await self._subscriber.aclose()
        logger.info("RedisPubSubManager shut down.")
 
    async def publish(self, user_id: str, message: dict) -> None:
        if self._publisher is None:
            raise RuntimeError("RedisPubSubManager has not been started.")
        channel = f"{_CHANNEL_PREFIX}:{user_id}"
        await self._publisher.publish(channel, json.dumps(message))
 
    async def subscribe(self, user_id: str) -> aioredis.client.PubSub:
        if self._subscriber is None:
            raise RuntimeError("RedisPubSubManager has not been started.")
        channel = f"{_CHANNEL_PREFIX}:{user_id}"
        pubsub = self._subscriber.pubsub()
        await pubsub.subscribe(channel)
        logger.debug("Subscribed to channel %s", channel)
        return pubsub
 
    async def unsubscribe(self, user_id: str, pubsub: aioredis.client.PubSub) -> None:
        channel = f"{_CHANNEL_PREFIX}:{user_id}"
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.debug("Unsubscribed from channel %s", channel)

    async def iter_messages(self, pubsub: aioredis.client.PubSub) -> AsyncIterator[dict]:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            try:
                yield json.loads(raw["data"])
            except json.JSONDecodeError:
                logger.warning("Received malformed JSON on pub/sub channel: %r", raw["data"])
    
    async def set_presence(self, user_id: str) -> None:
        if self._publisher is None:
            return
        key =  f"{_PRESENCE_PREFIX}:{user_id}"
        await self._publisher.set(key, "1", ex=_PRESENCE_TTL_SECONDS)
    
    async def clear_presence(self, user_id: str) -> None:
        if self._publisher is None:
            return
        key = f"{_PRESENCE_PREFIX}:{user_id}"
        await self._publisher.delete(key)