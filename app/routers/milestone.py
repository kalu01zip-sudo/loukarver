from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.milestone import (
    MilestoneCreate, MilestoneUpdate, MilestoneResponse, MilestonePaginatedResponse,
    MilestoneStepCreate, MilestoneStepUpdate, GenericResponse, MilestoneUnlock
)
from app.services.milestone import milestone_service

router = APIRouter(prefix="/milestone", tags=["Milestone"])

@router.post("/", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
async def create_milestone(payload: MilestoneCreate, current_user: dict = Depends(get_current_user)):
    """Create a new couple milestone goal."""
    try:
        return await milestone_service.create_milestone(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=MilestonePaginatedResponse)
async def list_milestones(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    pin: Optional[str] = Query(None, description="PIN to unlock private milestones"),
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """List all couple milestones. Private ones are masked unless correct PIN provided."""
    try:
        data, total = await milestone_service.get_milestones(current_user["id"], page, size, pin, timezone)
        return MilestonePaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(
    milestone_id: str, 
    pin: Optional[str] = Query(None, description="PIN to unlock if private"),
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific milestone."""
    try:
        milestone = await milestone_service.get_milestone_by_id(milestone_id, current_user["id"], pin, timezone)
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found.")
        return milestone
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(milestone_id: str, payload: MilestoneUpdate, current_user: dict = Depends(get_current_user)):
    """Update milestone details (Creator only)."""
    try:
        return await milestone_service.update_milestone(milestone_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{milestone_id}", response_model=GenericResponse)
async def delete_milestone(
    milestone_id: str, 
    pin: Optional[str] = Query(None, description="PIN required for private milestones"),
    current_user: dict = Depends(get_current_user)
):
    """Delete a milestone (Creator only)."""
    try:
        success = await milestone_service.delete_milestone(milestone_id, current_user["id"], pin)
        if not success:
            raise HTTPException(status_code=404, detail="Milestone not found or permission denied.")
        return GenericResponse(success=True, message="Milestone deleted successfully.")
    except ValueError as ve:
        raise HTTPException(status_code=403, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Step Operations ---

@router.post("/{milestone_id}/step", response_model=MilestoneResponse)
async def add_milestone_step(milestone_id: str, payload: MilestoneStepCreate, current_user: dict = Depends(get_current_user)):
    """Add a new step to a milestone (Creator only)."""
    try:
        return await milestone_service.add_step(milestone_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{milestone_id}/step/{step_id}", response_model=MilestoneResponse)
async def update_milestone_step(milestone_id: str, step_id: str, payload: MilestoneStepUpdate, current_user: dict = Depends(get_current_user)):
    """Update a specific milestone step (Creator only)."""
    try:
        return await milestone_service.update_step(milestone_id, step_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{milestone_id}/step/{step_id}", response_model=MilestoneResponse)
async def delete_milestone_step(
    milestone_id: str, 
    step_id: str, 
    pin: Optional[str] = Query(None, description="PIN required for private milestones"),
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific milestone step (Creator only)."""
    try:
        return await milestone_service.delete_step(milestone_id, step_id, current_user["id"], pin, timezone)
    except ValueError as ve:
        raise HTTPException(status_code=403, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{milestone_id}/step/{step_id}/toggle", response_model=MilestoneResponse)
async def toggle_step_completion(
    milestone_id: str, 
    step_id: str, 
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Toggle the completion status of a step (Both user and partner)."""
    try:
        return await milestone_service.toggle_step_completion(milestone_id, step_id, current_user["id"], timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{milestone_id}/unlock", response_model=MilestoneResponse)
async def unlock_milestone(milestone_id: str, payload: MilestoneUnlock, current_user: dict = Depends(get_current_user)):
    """Validate PIN and return full milestone details if correct."""
    try:
        milestone = await milestone_service.get_milestone_by_id(milestone_id, current_user["id"], payload.pin)
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found.")
        if milestone.get("is_locked"):
            raise HTTPException(status_code=403, detail="Incorrect PIN.")
        return milestone
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
