from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime
from enum import Enum

class PlaceCategory(str, Enum):
    HOME = "Home"
    TOGETHER = "Together"
    UPCOMING = "Upcoming"
    BUCKET = "Bucket"

class MomentType(str, Enum):
    PHOTO = "Photo"
    MILESTONE = "Milestone"
    NOTE = "Note"
    DATE = "Date"

class Moment(BaseModel):
    id: str
    type: MomentType
    content: str  # text or image_url
    caption: Optional[str] = None
    creator_id: str
    creator_name: str
    created_at: datetime

class MomentCreate(BaseModel):
    type: MomentType
    content: Optional[str] = None # text content
    caption: Optional[str] = None
    timezone: str = "UTC"

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "Photo",
                "content": "This can be a note or will be ignored if a file is uploaded",
                "caption": "Enjoying the sunset at the beach!",
                "timezone": "Asia/Dhaka"
            }
        }
    }

class PlaceBase(BaseModel):
    city: str
    country: str
    category: PlaceCategory
    description: Optional[str] = None
    visit_date: Optional[str] = Field(None, description="Format: mm.dd.yyyy")
    timezone: str = "UTC"

class PlaceCreate(PlaceBase):
    model_config = {
        "json_schema_extra": {
            "example": {
                "city": "Paris",
                "country": "France",
                "category": "Bucket",
                "description": "The city of love and lights.",
                "visit_date": "12.31.2026",
                "timezone": "Europe/Paris"
            }
        }
    }

class PlaceUpdate(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[PlaceCategory] = None
    description: Optional[str] = None
    visit_date: Optional[str] = None
    timezone: str = "UTC"

class PlaceResponse(BaseModel):
    id: str
    creator_id: str
    creator_name: str
    partner_id: str
    lat: float
    lng: float

    moments: List[Moment] = []
    created_at: datetime
    updated_at: datetime

class MapStats(BaseModel):
    total_countries: int
    total_cities: int
    together_count: int
    bucket_count: int
    upcoming_count: int
    home_count: int

class MapRoute(BaseModel):
    name: str
    points: List[dict] # List of {lat, lng, city}

class MapOverview(BaseModel):
    places: List[PlaceResponse]
    routes: List[MapRoute]
    stats: MapStats

class PlacePaginatedResponse(BaseModel):
    success: bool
    data: List[PlaceResponse]
    total: int
    page: int
    size: int

class GenericResponse(BaseModel):
    success: bool
    message: str
