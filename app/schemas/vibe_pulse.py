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
