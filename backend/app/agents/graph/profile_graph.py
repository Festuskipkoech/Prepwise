from pathlib import Path
 
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from qdrant_client import AsyncQdrantClient
 
from app.agents.prompts.profile_prompts import PROFILE_ANALYSIS_PROMPT
from app.agents.prompts.system_prompts import build_system_prompt
from app.agents.states.profile_state import ProfileState
from app.core.config import settings
from app.core.exceptions.profile import ProfileIndexError, ProfileNotFoundError
from app.repositories.profile_repository import ProfileRepository
from app.vector.chunks import chunk_profile
from app.vector.embeddings import embed_texts
from app.vector.qdrant_client import setup_collections
from app.vector.chunks import Chunk


async def load_and_chunk(state: ProfileState) -> ProfileState:
    profile_path = Path(settings.profile_path)

    if not profile_path.exists():
        raise ProfileNotFoundError()
    profile_text = profile_path.read_text(encoding="utf-8")
    chunks = chunk_profile(profile_text)

    return {
        **state,
        "profile_text": profile_text,
        "chunks": [
            {"id": c.id, "text": c.text, "metadata": c.metadata} for c in chunks
        ],
        "error": None,
    }
def make_embed_and_store(qdrant: AsyncQdrantClient):
    async def embed_and_store(state: ProfileState) -> ProfileState:
        chunks = state["chunks"]
        texts = [c["text"] for c in chunks]

        try:
            vectors = await embed_texts(texts)
        except Exception as exc:
            raise ProfileIndexError(f"Embedding failed: {exc}")
        repo = ProfileRepository(qdrant)
        await setup_collections(qdrant)
        await repo.delete_all_chunks()

        chunk_objects = [
            Chunk(id =c["id"], text=["text"], metadate=c["metadata"]) for c in chunks
        ]
        await repo.upsert_chunks(chunk_objects, vectors)

        return {
            **state,
            "vectors": vectors,
            "chunks_indexed": len(chunks)
        }
    return embed_and_store

def make_analyse(llm: BaseChatModel):
    async def analyse(state: ProfileState) -> ProfileState:
        profile_text = state["profile_text"]
        system = build_system_prompt(profile_text)
        prompt = PROFILE_ANALYSIS_PROMPT.format(profile_text = profile_text)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        response = await llm.ainvoke(messages)
        return {**state, "analysis": response.content}
    
    return analyse

def build_profile_graph(llm: BaseChatModel, qdrant: AsyncQdrantClient) -> StateGraph:
    graph = StateGraph(ProfileState)

    graph.add_node("load_and_chunk", load_and_chunk)
    graph.add_node("embed_and_store", make_embed_and_store(qdrant))
    graph.add_node("analyse", make_analyse(llm))
    
    graph.set_entry_point("load_and_chunk")
    graph.add_edge("load_and_chunk", "embed_and_store")
    graph.add_edge("embed_and_store", "analyse")
    graph.add_edge("analyse", END)

    return graph.compile()