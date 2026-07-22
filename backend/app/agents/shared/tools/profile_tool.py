import logging
 
from langchain_core.tools import tool
from qdrant_client import AsyncQdrantClient
from qdrant_client import models as qdrant_models
 
from app.vector.embeddings import JinaEmbeddings
from app.vector.qdrant_client import COLLECTION_PROFILE_CHUNKS
 
logger = logging.getLogger(__name__)
 
_TOP_K = 5

def build_profile_tool(
    user_id: str,
    qdrant: AsyncQdrantClient,
    embeddings: JinaEmbeddings
): 
    @tool
    async def get_profile_context(query: str) -> str:
        """Retrieve relevant sections of the user's professional profile
        based on the query. Use this whenever you need to know the user's
        skills, experience, projects, or background. Always call this before
        making claims about what the user knows or has done."""
        try:
            query_vector = await embeddings.aembed_query(query)
            results = await qdrant.search(
                collection_name=COLLECTION_PROFILE_CHUNKS,
                query_vector=query_vector,
                limit=_TOP_K,
                query_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="user_id",
                            match=qdrant_models.MatchValue(value=user_id),
                        )
                    ]
                ),
                with_payload=True,
            )

            if not results:
                return "No relevant profile sections found for this query."
            
            sections = []
            for hit in results:
                payload = hit.payload or {}
                chunk_type = payload.get("type", "unknown")
                name = payload.get("name", "")
                text = payload.get("text", "")
                sections.append(f"[{chunk_type.upper()}] {name}\n{text}")
            
            return "\n\n---\n\n".join(sections)
        
        except Exception:
            logger.exception(
                "get_profile_context failed for user %s query %r", user_id, query
            )
            return "Profile context could not be retrieved at this time."
    
    return get_profile_context

