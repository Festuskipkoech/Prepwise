import logging
 
from fastapi import Request
from qdrant_client import AsyncQdrantClient, models
 
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
COLLECTION_PROFILE_CHUNKS = "profile_chunks"
COLLECTION_PREP_CHUNKS = "prep_chunks"
 
_VECTOR_PARAMS = models.VectorParams(
    size=settings.embedding_dimensions,
    distance=models.Distance.COSINE,
)
  
def build_qdrant_client() -> AsyncQdrantClient:
    client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )
    logger.info(
        "Qdrant client initialised — %s:%d",
        settings.qdrant_host,
        settings.qdrant_port,
    )
    return client


async def setup_collections(client: AsyncQdrantClient) -> None:
    for name in (COLLECTION_PROFILE_CHUNKS, COLLECTION_PREP_CHUNKS):
        exists = await client.collection_exists(name)

        if not exists:
            await client.create_collection(
                collection_name=name,
                vectors_config=_VECTOR_PARAMS
            )
            logger.info("Qdrant collection created: %s", name)

        else:
            logger.info("Qdrant collection already exists: %s", name)

    # Payload index on user_id for every collection — enforces fast filtered
    # queries and ensures user isolation is performant at scale.
    for name in (COLLECTION_PROFILE_CHUNKS, COLLECTION_PREP_CHUNKS):
        await client.create_payload_index(
            collection_name=name,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        logger.debug("Payload index ensured on user_id for collection: %s", name)

def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant_client