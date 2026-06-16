from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.map import (
    PlaceCreate, PlaceUpdate, PlaceResponse, PlacePaginatedResponse,
    MapStats, MapOverview, MomentCreate, GenericResponse, PlaceCategory
)
from app.services.map import map_service

router = APIRouter(prefix="/map", tags=["Map"])

@router.post("/place", response_model=PlaceResponse, status_code=status.HTTP_201_CREATED)
async def create_place(payload: PlaceCreate, current_user: dict = Depends(get_current_user)):
    """Add a new meaningful place to your shared map."""
    try:
        return await map_service.create_place(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/places", response_model=PlacePaginatedResponse)
async def list_places(
    category: Optional[PlaceCategory] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """List all saved places with filtering and search."""
    try:
        data, total = await map_service.get_places(current_user["id"], category, search, page, size, timezone)
        return PlacePaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/place/{place_id}", response_model=PlaceResponse)
async def get_place(
    place_id: str, 
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get complete details about a specific location, including all moments."""
    try:
        place = await map_service.get_place_by_id(place_id, current_user["id"], timezone)
        if not place:
            raise HTTPException(status_code=404, detail="Place not found.")
        return place
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/place/{place_id}", response_model=PlaceResponse)
async def update_place(place_id: str, payload: PlaceUpdate, current_user: dict = Depends(get_current_user)):
    """Update a place's details. Only the creator can update."""
    try:
        return await map_service.update_place(place_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/place/{place_id}", response_model=GenericResponse)
async def delete_place(place_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a place from your map."""
    try:
        success = await map_service.delete_place(place_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Place not found or permission denied.")
        return GenericResponse(success=True, message="Place deleted successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/place/{place_id}/moment", response_model=PlaceResponse)
async def add_moment(
    place_id: str,
    type: str = Form(...),
    content: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    timezone: str = Form("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """Add a memory (photo, note, etc.) to a specific place."""
    try:
        payload = MomentCreate(type=type, content=content, caption=caption, timezone=timezone)
        return await map_service.add_moment(place_id, current_user["id"], payload, file)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=MapStats)
async def get_map_stats(
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics for the map section."""
    return await map_service.get_stats(current_user["id"])

@router.get("/overview", response_model=MapOverview)
async def get_map_overview(
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get data for map visualization, including places and calculated routes."""
    return await map_service.get_overview(current_user["id"], timezone)
