from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.vibe_card import (
    VibeCardDaily, VibeAnswerSubmit, VibeMatchResult, VibeStreakResponse, GenericResponse
)
from app.services.vibe_card import vibe_card_service

router = APIRouter(prefix="/vibecheck/cards", tags=["VibeCheck Cards"])

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

@router.get("/results/{partner_id}", response_model=VibeMatchResult)
async def get_vibe_results(
    partner_id: str,
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Compare today's results with a partner and see cumulative match score."""
    try:
        return await vibe_card_service.get_match_results(current_user["id"], partner_id, timezone)
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
