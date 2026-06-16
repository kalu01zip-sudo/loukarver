from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationPaginatedResponse, GenericResponse
)
from app.services.notification import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/schedule", response_model=NotificationResponse)
async def schedule_notification(payload: NotificationCreate, current_user: dict = Depends(get_current_user)):
    """Schedule a new notification for yourself or your partner."""
    return await notification_service.schedule_notification(current_user["id"], payload)

@router.get("/", response_model=NotificationPaginatedResponse)
async def list_my_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """List notifications received by the current user."""
    data, total = await notification_service.get_my_notifications(current_user["id"], page, size, timezone)
    return NotificationPaginatedResponse(success=True, data=data, total=total, page=page, size=size)

@router.patch("/{notification_id}/seen", response_model=GenericResponse)
async def mark_notification_seen(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a notification as seen."""
    success = await notification_service.mark_as_seen(notification_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return GenericResponse(success=True, message="Notification marked as seen.")
