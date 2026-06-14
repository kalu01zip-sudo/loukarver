from fastapi import APIRouter, Depends, HTTPException, status
from app.routers.auth import get_current_user
from app.schemas.lifecycle import (
    PeriodCreate, PeriodUpdate, PeriodResponseData,
    PhaseNoteCreate, PhaseNoteUpdate, PhaseNoteResponseData,
    LifeCycleResponse, LifeCycleStats
)
from app.services.lifecycle import lifecycle_service

router = APIRouter(prefix="/lifecycle", tags=["Life Cycle"])

@router.get("", response_model=LifeCycleResponse)
async def get_lifecycle_overview(current_user: dict = Depends(get_current_user)):
    """
    Retrieves the period cycle overview, including current phase, next period prediction, 
    recent history, and today's phase note.
    """
    try:
        data = await lifecycle_service.get_cycle_stats(current_user["id"])
        
        stats = None
        if data["stats"]:
            stats = LifeCycleStats(**data["stats"])
            
        history = [PeriodResponseData(**p) for p in data["history"]]
        
        current_note = None
        if data["current_note"]:
            current_note = PhaseNoteResponseData(**data["current_note"])
            
        return LifeCycleResponse(
            success=True,
            message="Overview retrieved successfully.",
            period_user_name=data.get("period_user_name"),
            stats=stats,
            recent_history=history,
            current_note=current_note
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Period CRUD ---

@router.post("/period", status_code=status.HTTP_201_CREATED)
async def add_period_start(payload: PeriodCreate, current_user: dict = Depends(get_current_user)):
    """Logs a new period start date."""
    try:
        result = await lifecycle_service.add_period(current_user["id"], payload)
        return {"success": True, "message": "Period start date logged.", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/period/{period_id}")
async def update_period_start(period_id: str, payload: PeriodUpdate, current_user: dict = Depends(get_current_user)):
    """Updates an existing period start date."""
    try:
        await lifecycle_service.update_period(current_user["id"], period_id, payload)
        return {"success": True, "message": "Period record updated."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/period/{period_id}")
async def delete_period_record(period_id: str, current_user: dict = Depends(get_current_user)):
    """Deletes a period start date record."""
    try:
        await lifecycle_service.delete_period(current_user["id"], period_id)
        return {"success": True, "message": "Period record deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Phase Notes CRUD ---

@router.post("/note", status_code=status.HTTP_201_CREATED)
async def add_phase_note(payload: PhaseNoteCreate, current_user: dict = Depends(get_current_user)):
    """Adds or updates a text note about the current phase for a specific date."""
    try:
        result = await lifecycle_service.add_note(current_user["id"], payload)
        return {"success": True, "message": "Phase note saved.", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/note/{note_id}")
async def update_phase_note(note_id: str, payload: PhaseNoteUpdate, current_user: dict = Depends(get_current_user)):
    """Updates the text of a previously logged phase note."""
    try:
        await lifecycle_service.update_note(current_user["id"], note_id, payload)
        return {"success": True, "message": "Phase note updated."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/note/{note_id}")
async def delete_phase_note(note_id: str, current_user: dict = Depends(get_current_user)):
    """Deletes a phase note."""
    try:
        await lifecycle_service.delete_note(current_user["id"], note_id)
        return {"success": True, "message": "Phase note deleted."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
