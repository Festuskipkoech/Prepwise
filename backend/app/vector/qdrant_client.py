from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

PROFILE_COLLECTION = "profile_chunks"
PREP_COLLECTION = "prep_chunks"
VECTOR_SIZE = 1024

def build_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

async def setup_collections(client: AsyncQdrantClient) -> None:
    existing = await client.get_collections()
    existing_names = {c.name for c in existing.collections}

    if PROFILE_COLLECTION not in existing_names:
        await client.create_collection(
            collection_name=PROFILE_COLLECTION,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE 
            ),
        )
    if PREP_COLLECTION not in existing_names:
        await client.create_collection(
            collection_name=PREP_COLLECTION,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
