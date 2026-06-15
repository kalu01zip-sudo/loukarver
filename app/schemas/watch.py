from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime

class WatchSessionBase(BaseModel):
    platform: str = Field(..., description="e.g., Netflix, Hulu, YouTube, etc.")
    show_name: str
    link: Optional[str] = None
    date: str = Field(..., description="Format: mm.dd.yyyy")
    time: str = Field(..., description="Format: 9:00 PM")
    timezone: str = Field(..., description="IANA Timezone, e.g., Asia/Dhaka")

class WatchSessionCreate(WatchSessionBase):
    model_config = {
        "json_schema_extra": {
            "example": {
                "platform": "Youtube",
                "show_name": "Shakira, Burna Boy - Dai Dai (Official Video)",
                "link": "https://youtu.be/fcnDmrtj6Sk?si=ENZkfrEQZeGwI0Dt",
                "date": "06.15.2026",
                "time": "09:00 PM",
                "timezone": "Asia/Dhaka"
            }
        }
    }

class WatchSessionUpdate(BaseModel):
    platform: Optional[str] = None
    show_name: Optional[str] = None
    link: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    timezone: Optional[str] = None

class WatchSessionRead(WatchSessionBase):
    id: str
    utc_timestamp: datetime
    # Acceptance
    is_accepted_user: bool = False
    is_accepted_partner: bool = False
    # Sync status
    is_ready_user: bool = False
    is_ready_partner: bool = False
    notification_fired: bool = False
    is_playing: bool = False
    play_triggered_at: Optional[datetime] = None
    # Meta
    created_at: datetime
    updated_at: datetime

class WatchSessionResponse(BaseModel):
    success: bool
    data: WatchSessionRead

class WatchSessionListResponse(BaseModel):
    success: bool
    data: List[WatchSessionRead]

class GenericResponse(BaseModel):
    success: bool
    message: str
