import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.db.redis import build_redis_pools, close_redis_pools
from app.db.session import AsyncSessionFactory
from app.llm.cache import register_system_prompt, run_cache_keepalive
from app.llm.client import build_llm_client
from app.routes import auth
from app.routes import profile as profile_router
from app.routes import websocket as websocket_router
from app.vector.embeddings import build_embeddings
from app.vector.qdrant_client import build_qdrant_client, setup_collections
from app.websocket.manager import ConnectionManager
from app.websocket.pubsub import RedisPubSubManager
from app.agents.prompts.classification import CLASSIFICATION_SYSTEM_PROMPT
from app.agents.prompts.normalisation import NORMALISATION_SYSTEM_PROMPT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s:%(filename)s:%(lineno)d %(message)s",
)
logger = logging.getLogger(__name__)

async def _check_dependencies(app: FastAPI) -> None:
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("PostgreSQL — ok")
    except Exception as e:
        raise RuntimeError(f"PostgreSQL unreachable: {e}")

    try:
        await app.state.redis_auth.ping()
        logger.info("Redis — ok")
    except Exception as e:
        raise RuntimeError(f"Redis unreachable: {e}")

    try:
        await app.state.qdrant_client.get_collections()
        logger.info("Qdrant — ok")
    except Exception as e:
        raise RuntimeError(f"Qdrant unreachable: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Redis — four isolated pools, one per logical database
    redis_pools = build_redis_pools()
    app.state.redis_auth = redis_pools["auth"]
    app.state.redis_cache = redis_pools["cache"]
    app.state.redis_ratelimit = redis_pools["ratelimit"]

    # Redis pub/sub — dedicated connection pair for publish/subscribe
    pubsub_manager = RedisPubSubManager()
    await pubsub_manager.startup()
    app.state.redis_pubsub = pubsub_manager

    # LLM clients
    app.state.llm_client = build_llm_client()

    # Embeddings
    app.state.embeddings = build_embeddings()

    # Qdrant
    qdrant = build_qdrant_client()
    await setup_collections(qdrant)
    app.state.qdrant_client = qdrant

    # WebSocket connection manager
    app.state.connection_manager = ConnectionManager()

    # nest both as context managers
    async with (
        AsyncPostgresSaver.from_conn_string(settings.langgraph_url) as checkpointer,
        AsyncPostgresStore.from_conn_string(settings.langgraph_url) as store,
    ):
        await checkpointer.setup()
        await store.setup()
        app.state.checkpointer = checkpointer
        app.state.store = store

        # Register system prompts for prompt cache keepalive
        register_system_prompt(CLASSIFICATION_SYSTEM_PROMPT)
        register_system_prompt(NORMALISATION_SYSTEM_PROMPT)

        # Start prompt cache keepalive background task
        asyncio.create_task(run_cache_keepalive(app.state.llm_client.large))

        await _check_dependencies(app)
        logger.info("Prepwise startup complete — env: %s", settings.app_env)

        yield

    # Shutdown
    await pubsub_manager.shutdown()
    await close_redis_pools(redis_pools)
    await app.state.qdrant_client.close()
    logger.info("Prepwise shutdown complete.")


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
app.include_router(profile_router.router, prefix="/api")
app.include_router(websocket_router.router)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}