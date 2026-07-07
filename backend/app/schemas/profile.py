from pydantic import BaseModel

class ProfileChunkMetadata(BaseModel):
    type: str
    project_name: str | None = None
    skill_name: str | None = None
    role_name: str | None = None
    stack_tags: list[str] = []
    depth_level: int | None = None
    scale_metrics: str | None = None
    company: str | None = None
    period: str | None = None

class ProfileChunk(BaseModel):
    id: str
    text: str
    metadata: ProfileChunkMetadata

class ProfileIndexResponse(BaseModel):
    message: str
    chunks_indexed: int
    analysis: str

class ProfileStatusResponse(BaseModel):
    indexed: bool
    chunks_count: int
    profile_path: str

class ProfileAnalysisResponse(BaseModel):
    analysis: str