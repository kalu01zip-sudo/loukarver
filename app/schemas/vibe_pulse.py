from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class PulseStatus(str, Enum):
    TALKING = "Talking"
    DATING = "Dating"
    SEEING = "Seeing"
    WORKING = "Working"
    EXCLUSIVE = "Exclusive"
    SERIOUS = "Serious"
    ALIGNED = "Aligned"
    FWB = "FWB"
    NONE = "None"

class VibePulseSetRequest(BaseModel):
    partner_id: str
    status: PulseStatus

class VibePulseResponse(BaseModel):
    partner_id: str
    partner_name: str
    my_status: PulseStatus
    partner_status: PulseStatus
    is_aligned_matched: bool
    updated_at: datetime

class VibePulseListResponse(BaseModel):
    success: bool
    data: List[VibePulseResponse]

class AlignedCheckResponse(BaseModel):
    success: bool
    is_aligned: bool
    partner_id: Optional[str] = None
    partner_name: Optional[str] = None
    message: str

# --- Flag System ---

class FlagCategory(str, Enum):
    GREEN = "Green"
    RED = "Red"
    YELLOW = "Yellow"

class FlagType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class VibeFlagCreate(BaseModel):
    partner_id: str
    category: FlagCategory
    type: FlagType
    text: str
    timezone: str = "UTC"

class VibeFlagUpdate(BaseModel):
    category: Optional[FlagCategory] = None
    type: Optional[FlagType] = None
    text: Optional[str] = None
    timezone: Optional[str] = None

class VibeFlagResponse(BaseModel):
    id: str
    user_id: str
    partner_id: str
    category: FlagCategory
    type: FlagType
    text: str
    created_at: datetime
    updated_at: datetime

class VibeFlagListResponse(BaseModel):
    success: bool
    data: List[VibeFlagResponse]
