import logging
from typing import List
 
import httpx
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel,ConfigDict, SecretStr
 
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
_JINA_ENDPOINT = "https://api.jina.ai/v1/embeddings"
_TASK_PASSAGE = "retrieval.passage"
_TASK_QUERY = "retrieval.query"

class JinaEmbeddings(BaseModel, Embeddings):
    """LangChain-compatible Jina embeddings wrapper.
 
    The langchain-community JinaEmbeddings class does not pass the task
    parameter to the API for v3+ models, which silently disables the
    task-specific LoRA adapters and degrades retrieval accuracy.
 
    This wrapper fixes that by explicitly passing:
        task=retrieval.passage  in embed_documents()
        task=retrieval.query    in embed_query()
 
    It conforms to LangChain's Embeddings base interface so it is a
    drop-in replacement for any other provider class. Switching providers
    requires changing only the class import and the EMBEDDING_MODEL env var.
    """
    model: str = "jina-embeddings-v4"
    dimensions: int = 2048
    api_key: SecretStr = SecretStr("")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, __context) -> None:
        object.__setattr__(self, "api_key", SecretStr(settings.jina_api_key))

    def _embed(self, texts: List[str], task:str) -> List[List[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "task": task,
            "dimensions": self.dimensions,
            "embedding_type": "float"
        }
        response = httpx.post(
            _JINA_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    async def  _aembed(self, texts: List[str], task: str) -> List[List[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "task": task,
            "dimensions": self.dimensions,
            "embedding_type": "float"
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _JINA_ENDPOINT,
                headers=headers,
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Embedding %d document(s) with task=%s", len(texts), _TASK_PASSAGE)
        return self._embed(texts, _TASK_PASSAGE)
    
    def embed_query(self, text: str) -> List[float]:
        logger.debug("Embedding query with task=%s", _TASK_QUERY)
        return self._embed([text], _TASK_QUERY)[0]
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Embedding %d document(s) async with task=%s", len(texts), _TASK_PASSAGE)
        return await self._aembed(texts, _TASK_PASSAGE)

    async def aembed_query(self, text: str) -> List[float]:
        logger.debug("Embedding query async with task=%s", _TASK_QUERY)
        result = await self._aembed([text], _TASK_QUERY)
        return result[0]

def build_embeddings() -> JinaEmbeddings:
    embeddings = JinaEmbeddings(
        model = settings.embedding_model,
        dimensions = settings.embedding_dimensions,
    )
    logger.info(
        "Embeddings initialised — model: %s  dimensions: %d",
        settings.embedding_model,
        settings.embedding_dimensions,
    )
    return embeddings



 