from typing import Any

import httpx

from app.core.config import settings

JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"

async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return[]
    
    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    payload : dict[str, Any] = {
        "model": JINA_MODEL,
        "input": texts,
        "task": "retrieval.passage",
    }

    async with httpx.AsyncClient(timeout = 60.0) as client:
        response = await client.post(JINA_EMBED_URL, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    return [item["embedding"] for item in data["data"]]

async def embed_query (text: str) -> list[float]:

    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": JINA_MODEL,
        "input": [text],
        "task" : "retrieval.query",
    }    
    async with httpx.AsyncClient(timeout = 60.0) as client:
        response = await client.post(JINA_EMBED_URL, headers=headers, json=payload)
        response.raise_for_status()
    
    data = response.json()
    return data["data"][0]["embedding"]