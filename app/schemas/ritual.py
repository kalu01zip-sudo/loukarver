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

class RitualCompleteResponse(BaseModel):
    success: bool
    already_completed_today: bool
    streak: int
    message: str

class RitualHistoryItem(BaseModel):
    date: str
    ritual_type: str
    completed: bool
    text: Optional[str] = None
    author_name: str
    is_partner: bool

class RitualHistoryResponse(BaseModel):
    data: List[RitualHistoryItem]
    total: int
    streak: int
