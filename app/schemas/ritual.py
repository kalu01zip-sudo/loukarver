from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class RitualType(str, Enum):
    appreciation = 'appreciation'
    checkin = 'checkin'
    letter = 'letter'
    voice = 'voice'
    photo = 'photo'
    goodnight = 'goodnight'

class RitualCompleteRequest(BaseModel):
    ritual_type: RitualType = Field(..., description="The type of ritual completed")
    timezone: str = Field("UTC", description="Client's timezone, e.g. America/Los_Angeles")
    text: Optional[str] = Field(None, description="Optional text submission for the ritual")
    time: Optional[str] = Field(None, description="Time of completion in 12h format (e.g. 08:30 AM)")
    time_name: Optional[str] = Field(None, description="Time name (e.g. morning, afternoon, evening, night)")

class RitualCompleteResponse(BaseModel):
    success: bool
    already_completed_today: bool
    streak: int
    message: str
    file_path: Optional[str] = None
    ritual_id: str
    time: Optional[str] = None
    time_name: Optional[str] = None

class RitualHistoryItem(BaseModel):
    ritual_id: str
    date: str
    ritual_type: str
    completed: bool
    text: Optional[str] = None
    file_path: Optional[str] = None
    author_name: str
    is_partner: bool
    partner_name: Optional[str] = None
    time: Optional[str] = None
    time_name: Optional[str] = None

class RitualHistoryResponse(BaseModel):
    data: List[RitualHistoryItem]
    total: int
    streak: int

class RitualUpdateResponse(BaseModel):
    success: bool
    message: str
    ritual_id: str
    file_path: Optional[str] = None
    streak: int
    time: Optional[str] = None
    time_name: Optional[str] = None

class RitualDeleteResponse(BaseModel):
    success: bool
    message: str
    streak: int
