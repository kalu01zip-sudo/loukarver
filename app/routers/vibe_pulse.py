from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.routers.auth import get_current_user
from app.schemas.vibe_pulse import (
    VibePulseSetRequest, VibePulseResponse, VibePulseListResponse, AlignedCheckResponse
)
from app.services.vibe_pulse import vibe_pulse_service

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
