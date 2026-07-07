from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from app.vector.chunks import Chunk
from app.vector.qdrant_client import PROFILE_COLLECTION

class ProfileRepository:
    def __init__(self, qdrant: AsyncQdrantClient) -> None:
        self.qdrant = qdrant

    async def count_chunks(self) -> int:
        result = await self.qdrant.count(collection_name=PROFILE_COLLECTION)
        return result.count

    async def upsert_chunks(
        self, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload=chunk.metadata,
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        await self.qdrant.upsert(
            collection_name=PROFILE_COLLECTION,
            points=points,
        )

    async def delete_all_chunks(self) -> None:
        await self.qdrant.delete_collection(collection_name=PROFILE_COLLECTION)

    async def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        chunk_type: str | None = None
    ) -> list[dict]:
        query_filter = None

        if chunk_type:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="type",
                        match=MatchValue(value=chunk_type),
                    )
                ]
            )

        results = await self.qdrant.search(
            collection_name=PROFILE_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {"text": hit.payload.get("text", ""), "metadata": hit.payload, "score": hit.score}
            for hit in results
        ]