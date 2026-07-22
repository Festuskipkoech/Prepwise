from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class ProfileUploadResponse(BaseModel):
    message: str
    chunks_indexed: int
    indexed_at: datetime

class ProfileStatusResponse(BaseModel):
    has_profile: bool
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    indexed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None