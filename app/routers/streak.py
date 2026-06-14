from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from app.routers.auth import get_current_user
from app.schemas.streak import StreakResponse, StreakWeeklyResponse, StreakPartnerResponse
from app.services.streak import streak_system

router = APIRouter(prefix="/streak", tags=["Streak"])

@router.get("", response_model=StreakResponse, status_code=status.HTTP_200_OK)
async def get_streak(timezone: str = Query("UTC"), current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.get_current_streak(current_user["id"], timezone)
        return StreakResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/weekly", response_model=StreakWeeklyResponse, status_code=status.HTTP_200_OK)
async def get_weekly_breakdown(timezone: str = Query("UTC"), current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.get_weekly_breakdown(current_user["id"], timezone)
        return StreakWeeklyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/partner", response_model=StreakPartnerResponse, status_code=status.HTTP_200_OK)
async def get_partner_streak(timezone: str = Query("UTC"), current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.get_partner_streak(current_user["id"], timezone)
        return StreakPartnerResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug", status_code=status.HTTP_200_OK)
async def get_streak_debug(current_user: dict = Depends(get_current_user)):
    try:
        dates = await streak_system.get_debug_history(current_user["id"])
        return {"dates": dates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
