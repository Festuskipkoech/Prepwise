import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_db, get_redis_auth
from app.core.config import settings
from app.core.exceptions.auth import InvalidTokenError
from app.core.security import decode_refresh_token
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    SessionListResponse,
    SessionResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60

def _get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_auth: Annotated[aioredis.Redis, Depends(get_redis_auth)],
) -> AuthService:
    return AuthService(db=db, redis_auth=redis_auth)

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/auth",
        max_age=COOKIE_MAX_AGE,
    )

def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/api/auth",
    )

@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(
    body: RegisterRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> MessageResponse:
    await service.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    return MessageResponse(message="Account created. Proceed to log in.")

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> TokenResponse:
    device_info = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    access_token, refresh_token = await service.login(
        email=body.email,
        password=body.password,
        device_info=device_info,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> TokenResponse:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_refresh_token:
        raise InvalidTokenError()

    new_access_token, new_refresh_token = await service.refresh(raw_refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=new_access_token)

@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> MessageResponse:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_refresh_token:
        raise InvalidTokenError()

    decoded = decode_refresh_token(raw_refresh_token)
    authorization = request.headers.get("authorization", "")
    access_token = authorization.removeprefix("Bearer ").strip()
    from app.core.security import decode_access_token
    decoded_access = decode_access_token(access_token)

    await service.logout(
        jti=decoded_access["jti"],
        token_hash=decoded["token_hash"],
    )
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully.")

@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    current_user: CurrentUser,
    service: Annotated[AuthService, Depends(_get_service)],
) -> MessageResponse:
    await service.logout_all(user_id=current_user.id)
    _clear_refresh_cookie(response)
    return MessageResponse(message="All sessions revoked.")

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(
    current_user: CurrentUser,
    service: Annotated[AuthService, Depends(_get_service)],
) -> SessionListResponse:
    sessions = await service.get_sessions(user_id=current_user.id)
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions]
    )

@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    service: Annotated[AuthService, Depends(_get_service)],
) -> MessageResponse:
    await service.revoke_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    return MessageResponse(message="Session revoked.")