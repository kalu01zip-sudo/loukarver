from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class DateMood(str, Enum):
    ROMANTIC = "Romantic"
    PLAYFUL = "Playful"
    ADVENTUROUS = "Adventurous"
    RELAXED = "Relaxed"
    INTIMATE = "Intimate"

class DateVibe(str, Enum):
    OUTDOORSY = "Outdoorsy"
    FOODIE = "Foodie"
    CULTURAL = "Cultural"
    NIGHTLIFE = "Nightlife"
    COZY = "Cozy"
    ACTIVE = "Active"

class DateStatus(str, Enum):
    PROPOSED = "Proposed"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    COMPLETED = "Completed"

class DateReview(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    text: str

class DateReviewRead(BaseModel):
    user_id: str
    user_name: str
    rating: int
    text: str

class DateReviewsResponse(BaseModel):
    success: bool
    data: List[DateReviewRead]

class DateBase(BaseModel):
    city_name: str
    mood: DateMood
    vibe: DateVibe
    time: str = Field(..., description="Time of the date, e.g. '09:00 PM'")
    date: str = Field(..., description="Date of the date, e.g. '12.25.2023'")
    timezone: str = Field(..., description="IANA Timezone, e.g., Asia/Dhaka")
    how_we_meet: str

class DateCreate(DateBase):
    pass

class DateUpdate(BaseModel):
    city_name: Optional[str] = None
    mood: Optional[DateMood] = None
    vibe: Optional[DateVibe] = None
    time: Optional[str] = None
    date: Optional[str] = None
    timezone: Optional[str] = None
    how_we_meet: Optional[str] = None

class DateResponse(DateBase):
    id: str
    creator_id: str
    partner_id: str
    status: DateStatus
    utc_timestamp: datetime
    created_at: datetime
    updated_at: datetime
    reviews: List[DateReview] = []
    notification_fired: bool = False

class DatePaginatedResponse(BaseModel):
    success: bool
    data: List[DateResponse]
    total: int
    page: int
    size: int

class DateRespond(BaseModel):
    accept: bool

class DateReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str

class GenericResponse(BaseModel):
    success: bool
    message: str
