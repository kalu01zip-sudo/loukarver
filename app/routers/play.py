from fastapi import APIRouter, Depends, status
from app.routers.auth import get_current_user
from app.schemas.play import PlayStatsResponse
from app.services.play import play_service

router = APIRouter(prefix="/play", tags=["Play"])

@router.get("", response_model=PlayStatsResponse, status_code=status.HTTP_200_OK)
async def get_play_stats(current_user: dict = Depends(get_current_user)):
    """
    Get Play section stats: viber name, streak days, and cumulated match percentage.
    """
    stats = await play_service.get_play_stats(current_user["id"])
    return PlayStatsResponse(**stats)
