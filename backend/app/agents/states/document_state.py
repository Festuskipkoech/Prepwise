from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

class DocumentState(TypedDict):
    job_id: UUID
    document_type: str
    jd_text: str
    retrieved_chunks: list[dict[str, Any]]
    jd_analysis: dict[str, Any]
    generated_content: dict[str, Any]
    error: str | None