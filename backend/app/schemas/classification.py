from typing import Literal

from pydantic import BaseModel, Field

EngineType = Literal["job", "prep", "document", "tracker"]
ExtendedEngineType = Literal["job", "prep", "document", "tracker", "unsupported"]

class ClassificationResult(BaseModel):
    engine_type: ExtendedEngineType
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str