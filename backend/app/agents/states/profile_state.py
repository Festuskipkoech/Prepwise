from typing import Any
from typing_extensions import TypedDict

class ProfileState(TypedDict):
    profile_text: str
    chunks: list[dict[str, Any]]
    vectors: list[list[float]]
    chunks_indexed: int
    analysis: str
    error: str | None