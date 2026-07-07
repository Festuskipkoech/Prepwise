from backend.app.schemas.auth import LoginResponse, LoginRequest
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    service = AuthService(db)
    token = await service.login(email=payload.email, password=payload.password)
    return LoginResponse(access_token=token)