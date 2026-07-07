from typing import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models.users import User
from app.db.session import AsyncSessionFactory
from app.core.exceptions.auth import InvalidTokenError
from app.repositories.user_repository import UserRepository
from app.services.document_service import DocumentService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.prep_service import PrepService
from app.services.tracker_service import TrackerService

bearer_scheme = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

def get_llm_client(request: Request):
    return request.app.state.llm_client

def get_qdrant(request: Request):
    return request.app.state.qdrant_client

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    email = decode_access_token(token)

    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(email)

    if user is None:
        raise InvalidTokenError()

    return user

def get_profile_service(request: Request) -> ProfileService:
    return ProfileService(
        llm=request.app.state.llm_client,
        qdrant=request.app.state.qdrant_client,
    )

def get_job_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JobService:
    return JobService(
        db=db,
        llm=request.app.state.llm_client,
    )

def get_document_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> DocumentService:
    return DocumentService(
        db=db,
        llm=request.app.state.llm_client,
        qdrant=request.app.state.qdrant_client,
    )

def get_prep_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PrepService:
    return PrepService(
        db=db,
        llm=request.app.state.llm_client,
    )

def get_tracker_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TrackerService:
    return TrackerService(
        db=db,
        llm=request.app.state.llm_client,
    )