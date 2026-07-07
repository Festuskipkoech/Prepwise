from fastapi import APIRouter, Depends
 
from app.core.dependencies import get_current_user, get_profile_service
from app.db.models.users import User
from app.schemas.profile import (
    ProfileAnalysisResponse,
    ProfileIndexResponse,
    ProfileStatusResponse,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/status", response_model=ProfileStatusResponse)
async def prfile_status(
    _:User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileStatusResponse:
    return await service.get_status()

@router.post("/index", repsonse_model = ProfileIndexResponse)
async def index_profile(
    _:User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileIndexResponse:
    return await service.index_profile()

@router.get("/analysis", response_model=ProfileAnalysisResponse)
async def analyse_profile(
    _: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileAnalysisResponse:
    return await service.anaylse_profile()