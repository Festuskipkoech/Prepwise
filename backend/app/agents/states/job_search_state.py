from typing import Any
from typing_extensions import TypedDict

class JobSearchState(TypedDict):
    query: str
    location: str
    limit: int
    profile_text: str
    raw_results: list[dict[str, Any]]
    scored_results: list[dict[str, Any]]
    error: str | None