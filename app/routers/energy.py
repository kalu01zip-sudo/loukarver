from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.routers.auth import get_current_user
from app.schemas.energy import (
    EnergyCreate, EnergyUpdate, EnergyPatchShare,
    EnergyResponse, EnergyListResponse, GenericResponse
)
from app.services.energy import energy_service

router = APIRouter(prefix="/energy", tags=["Energy"])

@router.post("", response_model=EnergyResponse, status_code=status.HTTP_201_CREATED)
async def create_energy_log(payload: EnergyCreate, current_user: dict = Depends(get_current_user)):
    """Create a new energy log."""
    try:
        result = await energy_service.create_energy_log(current_user["id"], payload)
        return EnergyResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=EnergyListResponse)
async def get_energy_logs(current_user: dict = Depends(get_current_user)):
    """Get all energy logs for the current user."""
    try:
        results = await energy_service.get_energy_logs(current_user["id"])
        return EnergyListResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/partner", response_model=EnergyListResponse)
async def get_partner_energy(current_user: dict = Depends(get_current_user)):
    """Get the partner's shared energy logs."""
    try:
        results = await energy_service.get_partner_energy(current_user["id"])
        return EnergyListResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{log_id}", response_model=EnergyResponse)
async def get_energy_log(log_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific energy log."""
    try:
        result = await energy_service.get_energy_log(log_id, current_user["id"])
        if not result:
            raise HTTPException(status_code=404, detail="Energy log not found")
        return EnergyResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{log_id}", response_model=EnergyResponse)
async def update_energy_log(log_id: str, payload: EnergyUpdate, current_user: dict = Depends(get_current_user)):
    """Update an energy log."""
    try:
        result = await energy_service.update_energy_log(log_id, current_user["id"], payload)
        if not result:
            raise HTTPException(status_code=404, detail="Energy log not found")
        return EnergyResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{log_id}", response_model=GenericResponse)
async def delete_energy_log(log_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an energy log."""
    try:
        success = await energy_service.delete_energy_log(log_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Energy log not found")
        return GenericResponse(success=True, message="Energy log deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{log_id}/share", response_model=GenericResponse)
async def patch_share_status(log_id: str, payload: EnergyPatchShare, current_user: dict = Depends(get_current_user)):
    """Update the share status of an energy log."""
    try:
        success = await energy_service.patch_share_status(log_id, current_user["id"], payload)
        if not success:
            raise HTTPException(status_code=404, detail="Energy log not found")
        return GenericResponse(success=True, message="Share status updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
