from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.db.redis import build_redis_pools, close_redis_pools
from app.llm.client import build_llm_client
from app.routes import auth
from app.vector.qdrant_client import build_qdrant_client, setup_collections
from app.db.session import AsyncSessionFactory

async def _check_dependencies(app: FastAPI) -> None:
    # PostgreSQL
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"PostgreSQL unreachable: {e}")

    # Redis
    try:
        await app.state.redis_auth.ping()
    except Exception as e:
        raise RuntimeError(f"Redis unreachable: {e}")

    # Qdrant
    try:
        await app.state.qdrant_client.get_collections()
    except Exception as e:
        raise RuntimeError(f"Qdrant unreachable: {e}")
    
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    redis_pools = build_redis_pools()
    app.state.redis_auth = redis_pools["auth"]
    app.state.redis_pubsub = redis_pools["pubsub"]
    app.state.redis_cache = redis_pools["cache"]
    app.state.redis_ratelimit = redis_pools["ratelimit"]

    app.state.llm_client = build_llm_client()

    qdrant = build_qdrant_client()
    await setup_collections(qdrant)
    app.state.qdrant_client = qdrant

    await _check_dependencies(app)

    yield

    await close_redis_pools(redis_pools)
    await app.state.qdrant_client.close()

app = FastAPI(
    title="Prepwise",
    docs_url="/api/docs" if settings.app_env == "development" else None,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}