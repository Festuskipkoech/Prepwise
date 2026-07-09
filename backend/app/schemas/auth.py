import re
import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, field_validator, field_serializer

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SessionResponse(BaseModel):
    id: uuid.UUID
    device_info: Optional[str]
    ip_address: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip(cls, value: Any) -> Optional[str]:
        return str(value) if value is not None else None

class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]

class MessageResponse(BaseModel):
    message: str