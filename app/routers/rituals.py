from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.routers.auth import get_current_user
from app.schemas.ritual import RitualCompleteRequest, RitualCompleteResponse, RitualHistoryResponse
from app.services.streak import streak_system

router = APIRouter(prefix="/rituals", tags=["Rituals"])

@router.post("/complete", response_model=RitualCompleteResponse, status_code=status.HTTP_200_OK)
async def complete_ritual(payload: RitualCompleteRequest, current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.mark_ritual_complete(current_user["id"], payload)
        return RitualCompleteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=RitualHistoryResponse, status_code=status.HTTP_200_OK)
async def get_history(page: int = Query(1, ge=1), limit: int = Query(30, ge=1), timezone: str = Query("UTC"), current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.get_history(current_user["id"], page, limit, timezone)
        return RitualHistoryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
