from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.vibe_card import (
    VibeCardDaily, VibeAnswerSubmit, VibeMatchResult, VibeMultiMatchResult,
    VibeStreakResponse, GenericResponse, VibeHistoryPaginatedResponse
)
from app.services.vibe_card import vibe_card_service

router = APIRouter(prefix="/vibecheck/cards", tags=["VibeCheck Cards"])

@router.get("/history", response_model=VibeHistoryPaginatedResponse)
async def get_vibe_card_history(
    partner_id: Optional[str] = Query(None),
    category: str = Query("All", enum=["All", "Matched", "Differed"]),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Fetch history of answers between user and partners. If partner_id is not provided, shows all partners."""
    try:
        data, total = await vibe_card_service.get_history(
            current_user["id"], partner_id, category, page, size
        )
        return VibeHistoryPaginatedResponse(
            success=True,
            data=data,
            total=total,
            page=page,
            size=size,
            category=category
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/daily", response_model=VibeCardDaily)
async def get_daily_cards(
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Fetch today's 3 'This or That' questions."""
    questions = await vibe_card_service.get_daily_questions(current_user["id"], timezone)
    from datetime import datetime
    import zoneinfo
    try:
        tz = zoneinfo.ZoneInfo(timezone)
    except:
        tz = zoneinfo.ZoneInfo("UTC")
    today_str = datetime.now(tz).strftime("%m.%d.%Y")
    
    return {"date": today_str, "questions": questions}

@router.post("/answer", response_model=GenericResponse)
async def submit_vibe_answers(
    payload: VibeAnswerSubmit,
    current_user: dict = Depends(get_current_user)
):
    """Submit your answers for today's Vibe Cards."""
    try:
        return await vibe_card_service.submit_answers(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results", response_model=VibeMultiMatchResult)
async def get_vibe_results(
    partner_id: Optional[str] = Query(None),
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Compare today's results with partners. If partner_id is not provided, shows all connected partners who answered today."""
    try:
        results = await vibe_card_service.get_match_results(current_user["id"], partner_id, timezone)
        return VibeMultiMatchResult(success=True, data=results)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streak", response_model=VibeStreakResponse)
async def get_vibe_streak(
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Get your current Vibe Card answering streak."""
    return await vibe_card_service.get_streak(current_user["id"], timezone)
