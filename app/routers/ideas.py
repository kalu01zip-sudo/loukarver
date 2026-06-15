from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List

from app.routers.auth import get_current_user
from app.schemas.ideas import (
    IdeaCreate, IdeaUpdate, IdeaRead, IdeaListResponse,
    IdeaProgressResponse, IdeaProgressPaginatedResponse,
    CategoryListResponse, GenericResponse
)
from app.services.ideas import idea_service

router = APIRouter(prefix="/ideas", tags=["Ideas"])

@router.get("/browse", response_model=IdeaListResponse)
async def get_browse_ideas(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get a paginated list of global and personalized ideas."""
    try:
        data, total = await idea_service.get_browse_ideas(current_user["id"], page, size)
        return IdeaListResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=CategoryListResponse)
async def get_categories(current_user: dict = Depends(get_current_user)):
    """Get all unique categories from global and personalized ideas."""
    try:
        data = await idea_service.get_categories(current_user["id"])
        return CategoryListResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Personalized Ideas CRUD ---

@router.post("/personalized", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
async def create_personalized_idea(payload: IdeaCreate, current_user: dict = Depends(get_current_user)):
    """Create a new personalized idea visible only to the couple."""
    try:
        await idea_service.create_personalized_idea(current_user["id"], payload)
        return GenericResponse(success=True, message="Personalized idea created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/personalized/{idea_id}", response_model=GenericResponse)
async def update_personalized_idea(idea_id: str, payload: IdeaUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing personalized idea."""
    try:
        result = await idea_service.update_personalized_idea(idea_id, current_user["id"], payload)
        if not result:
            raise HTTPException(status_code=404, detail="Idea not found or unauthorized")
        return GenericResponse(success=True, message="Personalized idea updated.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/personalized/{idea_id}", response_model=GenericResponse)
async def delete_personalized_idea(idea_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a personalized idea."""
    try:
        success = await idea_service.delete_personalized_idea(idea_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Idea not found or unauthorized")
        return GenericResponse(success=True, message="Personalized idea deleted.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Idea Selection & Progress ---

@router.post("/select/{idea_id}", response_model=IdeaProgressResponse)
async def select_idea(
    idea_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Add an idea to the couple's list (Pending Acceptance)."""
    try:
        result = await idea_service.select_idea(idea_id, current_user["id"])
        return IdeaProgressResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/active/{progress_id}/accept", response_model=IdeaProgressResponse)
async def accept_idea(progress_id: str, current_user: dict = Depends(get_current_user)):
    """Accept a selected idea. Countdown starts when both partners accept."""
    try:
        result = await idea_service.accept_idea(progress_id, current_user["id"])
        return IdeaProgressResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=IdeaProgressPaginatedResponse)
async def get_active_ideas(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    viewer_timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get the couple's list of active ideas (Not expired, Not fully completed)."""
    try:
        data, total = await idea_service.get_paginated_progress(current_user["id"], "active", page, size, viewer_timezone)
        return IdeaProgressPaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/completed", response_model=IdeaProgressPaginatedResponse)
async def get_completed_ideas(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    viewer_timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get the couple's list of completed ideas."""
    try:
        data, total = await idea_service.get_paginated_progress(current_user["id"], "completed", page, size, viewer_timezone)
        return IdeaProgressPaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/incomplete", response_model=IdeaProgressPaginatedResponse)
async def get_incomplete_ideas(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    viewer_timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get the couple's list of expired/incomplete ideas."""
    try:
        data, total = await idea_service.get_paginated_progress(current_user["id"], "incomplete", page, size, viewer_timezone)
        return IdeaProgressPaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/active/{progress_id}/done", response_model=IdeaProgressResponse)
async def mark_idea_done(progress_id: str, current_user: dict = Depends(get_current_user)):
    """Mark an active idea as done for the current user."""
    try:
        result = await idea_service.mark_idea_done(progress_id, current_user["id"])
        return IdeaProgressResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
