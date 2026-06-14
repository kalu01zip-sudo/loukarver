from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# --- Mood List Schemas ---

class MoodListItem(BaseModel):
    id: str
    name: str
    symbol: str
    order_index: int
    is_active: bool

class MoodListCreate(BaseModel):
    name: str
    symbol: str
    order_index: int
    is_active: bool = True

class MoodListUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None

class MoodListResponse(BaseModel):
    success: bool
    data: List[MoodListItem]

# --- Mood Input Schemas ---

class MoodLogCreate(BaseModel):
    mood_id: str = Field(..., description="The ID of the mood from the available mood list")

class MoodLogItem(BaseModel):
    id: str
    user_id: str
    mood_id: str
    mood_name: str
    mood_symbol: str
    created_at: datetime

class MoodHistoryResponse(BaseModel):
    success: bool
    data: List[MoodLogItem]

class MoodLogUpdate(BaseModel):
    mood_id: str = Field(..., description="The ID of the new mood")

# --- Current Mood Schemas ---

class CurrentMoodState(BaseModel):
    mood_name: str
    mood_symbol: str
    updated_at: datetime
    is_partner: bool
    author_name: str

class CurrentMoodResponse(BaseModel):
    success: bool
    data: List[CurrentMoodState]

class GenericResponse(BaseModel):
    success: bool
    message: str
