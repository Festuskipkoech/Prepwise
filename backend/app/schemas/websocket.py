from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

EngineType = Literal["job", "prep", "document", "tracker"]

class InboundMessage(BaseModel):
    type: Literal["message"] = "message"
    chat_id: UUID | None = None
    engine_type: EngineType | None = None
    content: str = Field(..., min_length=1, max_length=32_000)

class OutboundToken(BaseModel):
    type: Literal["token"] = "token"
    content: str

class OutboundStatus(BaseModel):
    type: Literal["status"] = "status"
    content: str

class OutboundThinking(BaseModel):
    type: Literal["thinking"] = "thinking"
    content: str

class OutboundDone(BaseModel):
    type: Literal["done"] = "done"
    chat_id: str
    engine_type: EngineType
    title: str | None = None

class OutboundError(BaseModel):
    type: Literal["error"] = "error"
    content: str

OutboundMessage = (
    OutboundToken
    | OutboundStatus
    | OutboundThinking
    | OutboundDone
    | OutboundError
)