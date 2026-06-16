from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.dates import (
    DateCreate, DateUpdate, DateResponse, DatePaginatedResponse,
    DateRespond, DateReviewCreate, GenericResponse, DateReviewsResponse
)
from app.services.dates import date_service

router = APIRouter(prefix="/dates", tags=["Dates"])

@router.post("/", response_model=DateResponse, status_code=status.HTTP_201_CREATED)
async def create_date(payload: DateCreate, current_user: dict = Depends(get_current_user)):
    """Create a new proposed date for your partner."""
    try:
        return await date_service.create_date(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=DatePaginatedResponse)
async def list_dates(
    status: Optional[str] = Query(None, description="Filter by status (Proposed, Accepted, Rejected, Completed)"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """List all dates for the couple (Paginated)."""
    try:
        data, total = await date_service.get_dates(current_user["id"], status, page, size, timezone)
        return DatePaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{date_id}", response_model=DateResponse)
async def get_date(
    date_id: str, 
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific date."""
    try:
        date = await date_service.get_date_by_id(date_id, current_user["id"], timezone)
        if not date:
            raise HTTPException(status_code=404, detail="Date not found.")
        return date
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{date_id}", response_model=DateResponse)
async def update_date(date_id: str, payload: DateUpdate, current_user: dict = Depends(get_current_user)):
    """Update a proposed date. Only the creator can update."""
    try:
        return await date_service.update_date(date_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{date_id}", response_model=GenericResponse)
async def delete_date(date_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a date. Only the creator can delete."""
    try:
        success = await date_service.delete_date(date_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Date not found or you are not the creator.")
        return GenericResponse(success=True, message="Date deleted successfully.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{date_id}/respond", response_model=DateResponse)
async def respond_to_date(date_id: str, payload: DateRespond, current_user: dict = Depends(get_current_user)):
    """Accept or reject a proposed date. Only the partner can respond."""
    try:
        return await date_service.respond_to_date(date_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{date_id}/complete", response_model=DateResponse)
async def complete_date(date_id: str, current_user: dict = Depends(get_current_user)):
    """Mark an accepted date as completed. Can only be done after the date time."""
    try:
        return await date_service.complete_date(date_id, current_user["id"])
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{date_id}/review", response_model=DateResponse)
async def add_review(date_id: str, payload: DateReviewCreate, current_user: dict = Depends(get_current_user)):
    """Add a review to a completed date."""
    try:
        return await date_service.add_review(date_id, current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{date_id}/reviews", response_model=DateReviewsResponse)
async def get_date_reviews(
    date_id: str, 
    timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"),
    current_user: dict = Depends(get_current_user)
):
    """Get both user and partner reviews for a specific date."""
    try:
        reviews = await date_service.get_date_reviews(date_id, current_user["id"], timezone)
        return DateReviewsResponse(success=True, data=reviews)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
