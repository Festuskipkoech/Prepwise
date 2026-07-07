from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.llm.cache import CacheKeepalive
from app.llm.client import build_llm_client
from app.repositories.profile_repository import ProfileRepository
from app.routes import auth, documents, jobs, profile, prep, tracker
from app.services.profile_service import ProfileService
from app.vector.qdrant_client import build_qdrant_client, setup_collections

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.llm_client = build_llm_client()

    qdrant = build_qdrant_client()
    await setup_collections(qdrant)
    app.state.qdrant_client = qdrant

    profile_text = Path(settings.profile_path).read_text(encoding="utf-8")
    app.state.profile_text = profile_text

    keepalive = CacheKeepalive(profile_text=profile_text)
    keepalive.start()
    app.state.cache_keepalive = keepalive

    profile_repo = ProfileRepository(qdrant)
    count = await profile_repo.count_chunks()
    if count == 0:
        profile_service = ProfileService(llm = app.state.llm_client, qdrant = qdrant)
        await profile_service.index_profile()

    yield

    keepalive.stop()
    await app.stateqdrant_client.close()

app = FastAPI(
    title="Prepwise",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(documents.router)
app.include_router(prep.router)
app.include_router(tracker.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}