from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class NotificationType(str, Enum):
    TRIP_REMINDER = "Trip Reminder"
    ANNIVERSARY = "Anniversary"
    MILESTONE = "Milestone"
    SYSTEM = "System"
    MAP_UPDATE = "Map Update"

class NotificationStatus(str, Enum):
    SCHEDULED = "Scheduled"
    DELIVERED = "Delivered"
    SEEN = "Seen"
    FAILED = "Failed"

class NotificationBase(BaseModel):
    title: str
    message: str
    type: NotificationType
    scheduled_for: datetime
    timezone: str = "UTC"

class NotificationCreate(NotificationBase):
    recipient_id: str # Can be self or partner

class NotificationResponse(NotificationBase):
    id: str
    sender_id: str
    recipient_id: str
    status: NotificationStatus
    created_at: datetime
    delivered_at: Optional[datetime] = None

class NotificationPaginatedResponse(BaseModel):
    success: bool
    data: List[NotificationResponse]
    total: int
    page: int
    size: int

class GenericResponse(BaseModel):
    success: bool
    message: str
