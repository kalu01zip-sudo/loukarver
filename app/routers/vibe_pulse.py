from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.routers.auth import get_current_user
from app.schemas.vibe_pulse import (
    VibePulseSetRequest, VibePulseResponse, VibePulseListResponse, AlignedCheckResponse,
    VibeFlagCreate, VibeFlagUpdate, VibeFlagResponse, VibeFlagListResponse
)
from app.schemas.vibe_card import PulseAnalyticsResponse
from app.services.vibe_pulse import vibe_pulse_service
from app.services.vibe_card import vibe_card_service

router = APIRouter(prefix="/ladder", tags=["Vibe Pulse"])

@router.post("", response_model=VibePulseResponse)
async def set_vibe_pulse(payload: VibePulseSetRequest, current_user: dict = Depends(get_current_user)):
    """Set relationship status for a Vibe partner."""
    try:
        return await vibe_pulse_service.set_pulse(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=VibePulseListResponse)
async def list_vibe_pulses(current_user: dict = Depends(get_current_user)):
    """List all pulse statuses set by the user."""
    try:
        data = await vibe_pulse_service.get_all_pulses(current_user["id"])
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{partner_id}", response_model=VibePulseResponse)
async def get_vibe_pulse_status(partner_id: str, current_user: dict = Depends(get_current_user)):
    """Get relationship status with a specific partner."""
    try:
        return await vibe_pulse_service.get_pulse_status(current_user["id"], partner_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check-aligned/{partner_id}", response_model=AlignedCheckResponse)
async def check_aligned_connection(partner_id: str, current_user: dict = Depends(get_current_user)):
    """Check if both user and partner have set 'Aligned' status with each other."""
    try:
        return await vibe_pulse_service.check_aligned_connection(current_user["id"], partner_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{partner_id}")
async def delete_vibe_pulse(partner_id: str, current_user: dict = Depends(get_current_user)):
    """Reset relationship status with a partner."""
    try:
        success = await vibe_pulse_service.delete_pulse(current_user["id"], partner_id)
        if not success:
             raise HTTPException(status_code=404, detail="Pulse status not found.")
        return {"success": True, "message": "Pulse status reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights/analytics", response_model=PulseAnalyticsResponse)
async def get_pulse_analytics(partner_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Fetch detailed matching analytics for vibe partners."""
    try:
        data = await vibe_card_service.get_pulse_analytics(current_user["id"], partner_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Flag System Endpoints ---

@router.post("/flags", response_model=VibeFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(payload: VibeFlagCreate, current_user: dict = Depends(get_current_user)):
    """Create a relationship flag (Green/Red/Yellow)."""
    try:
        return await vibe_pulse_service.create_flag(current_user["id"], payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flags", response_model=VibeFlagListResponse)
async def list_my_flags(partner_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List flags created by the authenticated user."""
    try:
        data = await vibe_pulse_service.get_my_flags(current_user["id"], partner_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flags/partner/{partner_id}", response_model=VibeFlagListResponse)
async def list_partner_flags(partner_id: str, current_user: dict = Depends(get_current_user)):
    """List PUBLIC flags created by a partner about the authenticated user."""
    try:
        data = await vibe_pulse_service.get_partner_flags(current_user["id"], partner_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/flags/{flag_id}", response_model=VibeFlagResponse)
async def update_flag(flag_id: str, payload: VibeFlagUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing flag."""
    try:
        return await vibe_pulse_service.update_flag(current_user["id"], flag_id, payload)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/flags/{flag_id}")
async def delete_flag(flag_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a flag."""
    try:
        success = await vibe_pulse_service.delete_flag(current_user["id"], flag_id)
        if not success:
            raise HTTPException(status_code=404, detail="Flag not found.")
        return {"success": True, "message": "Flag deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
