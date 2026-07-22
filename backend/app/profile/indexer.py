import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client import models as qdrant_models

from app.vector.chunks import ProfileChunk, parse_profile_chunks
from app.vector.embeddings import JinaEmbeddings
from app.vector.qdrant_client import COLLECTION_PROFILE_CHUNKS

logger = logging.getLogger(__name__)

_BATCH_SIZE = 32

def _chunk_to_point(chunk: ProfileChunk, vector: list[float]) -> qdrant_models.PointStruct:
    return qdrant_models.PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={
            "user_id": chunk.user_id,
            "type": chunk.type,
            "name": chunk.name,
            "text": chunk.text,
            "stack_tags": chunk.stack_tags,
            "depth_level": chunk.depth_level,
            "period": chunk.period,
        },
    )

async def _delete_user_vectors(client: AsyncQdrantClient, user_id: str) -> None:
    await client.delete(
        collection_name=COLLECTION_PROFILE_CHUNKS,
        points_selector=qdrant_models.FilterSelector(
            filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="user_id",
                        match=qdrant_models.MatchValue(value=user_id),
                    )
                ]
            )
        ),
    )
    logger.debug("Deleted existing profile vectors for user %s", user_id)

async def _embed_chunks(
    chunks: list[ProfileChunk],
    embeddings: JinaEmbeddings,
) -> list[qdrant_models.PointStruct]:
    points: list[qdrant_models.PointStruct] = []

    for i in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[i : i + _BATCH_SIZE]
        texts = [chunk.text for chunk in batch]
        vectors = await embeddings.aembed_documents(texts)
        for chunk, vector in zip(batch, vectors):
            points.append(_chunk_to_point(chunk, vector))

    return points

async def _upsert_points(
    client: AsyncQdrantClient,
    points: list[qdrant_models.PointStruct],
) -> None:
    for i in range(0, len(points), _BATCH_SIZE):
        batch = points[i : i + _BATCH_SIZE]
        await client.upsert(
            collection_name=COLLECTION_PROFILE_CHUNKS,
            points=batch,
            wait=True,
        )
    logger.debug("Upserted %d vectors to %s", len(points), COLLECTION_PROFILE_CHUNKS)

async def index_profile(
    user_id: str,
    normalised_md: str,
    qdrant: AsyncQdrantClient,
    embeddings: JinaEmbeddings,
) -> int:
    """Parse, embed, and upsert a normalised profile into Qdrant.

    Deletes any existing vectors for the user before writing new ones.
    Does not touch the database — marking indexed_at is the caller's
    responsibility via ProfileRepository.mark_indexed().
    Returns the number of chunks indexed.
    """
    await _delete_user_vectors(qdrant, user_id)

    chunks = parse_profile_chunks(normalised_md, user_id)
    if not chunks:
        raise ValueError("No chunks could be parsed from the normalised profile.")

    points = await _embed_chunks(chunks, embeddings)
    await _upsert_points(qdrant, points)

    logger.info("Indexed %d chunks for user %s", len(chunks), user_id)
    return len(chunks)