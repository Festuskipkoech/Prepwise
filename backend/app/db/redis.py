import redis.asyncio as aioredis

from app.core.config import settings

def _make_pool(db: int) -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url,
        db=db,
        password=settings.redis_password,
        decode_responses=True,
    )

def build_redis_pools() -> dict[str, aioredis.Redis]:
    return {
        "auth": _make_pool(settings.redis_db_auth),
        "pubsub": _make_pool(settings.redis_db_pubsub),
        "cache": _make_pool(settings.redis_db_cache),
        "ratelimit": _make_pool(settings.redis_db_ratelimit),
    }

async def close_redis_pools(pools: dict[str, aioredis.Redis]) -> None:
    for pool in pools.values():
        await pool.aclose()