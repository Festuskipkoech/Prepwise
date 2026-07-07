from pathlib import Path
 
from langchain_core.language_models.chat_models import BaseChatModel
from qdrant_client import AsyncQdrantClient
 
from app.agents.graph.profile_graph import build_profile_graph
from app.agents.prompts.profile_prompts import PROFILE_ANALYSIS_PROMPT
from app.agents.prompts.system_prompts import build_system_prompt
from app.core.config import settings
from app.exceptions.profile import ProfileNotFoundError
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import (
    ProfileAnalysisResponse,
    ProfileIndexResponse,
    ProfileStatusResponse,
)

INITIAL_STATE = {
    "profile_text": "",
    "chunks": [],
    "vectors": [],
    "chunks_indexed": 0,
    "analysis": "",
    "error": None,
}

class ProfileService:
    def __init__(self, llm: BaseChatModel, qdrant: AsyncQdrantClient) -> None:
        self.llm = llm
        self.qdrant = qdrant
        self.repo = ProfileRepository(qdrant)
    
    async def get_status(self) -> ProfileStatusResponse:
        profile_path = Path(settings.profile_path)
        count = await self.repo.count_chunks()
        return ProfileStatusResponse(
            indexed = count > 0,
            chunks_count = count,
            profile_path = str(profile_path),
        )
    async def index_profile(self) -> ProfileIndexResponse:
        profile_path = Path(settings.profile_path)
        if not profile_path.exists():
            raise ProfileNotFoundError()
        graph = build_profile_graph(llm = self.llm, qdrant = self.qdrant)
        result = await graph.ainvoke(INITIAL_STATE)
        return ProfileIndexResponse(
            message= "Profile indexed successfully",
            chunks_indexed=result["chunks_indexed"],
            analysis = result["analysis"],
        )
    async def anaylse_profile(self) -> ProfileAnalysisResponse:
        profile_path = Path(settings.profile_path)
        if not profile_path.exists:
            raise ProfileNotFoundError()
        profile_text = profile_path.read_text(encoding="utf-8")
        system = build_system_prompt(profile_text)
        prompt = PROFILE_ANALYSIS_PROMPT.format(profile_text=profile_text)

        messages= [
            {"role": "system", "content": system},
            {"role": "system", "content": prompt},
        ]
        response = await self.llm.ainvoke(messages)
        return ProfileAnalysisResponse(analysis=response.content)