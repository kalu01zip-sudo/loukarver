from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class DateStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PROPOSED_CHANGES = "proposed_changes"

class VibeDateCreate(BaseModel):
    partner_id: str
    where: str
    date: str  # Format: YYYY-MM-DD
    time: str  # Format: HH:MM
    how_we_meet: str
    note: Optional[str] = None
    timezone: str

class VibeDateUpdate(BaseModel):
    where: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    how_we_meet: Optional[str] = None
    note: Optional[str] = None
    timezone: Optional[str] = None

class VibeDateResponse(BaseModel):
    id: str
    proposer_id: str
    partner_id: str
    proposer_name: str
    partner_name: str
    where: str
    date: str
    time: str
    how_we_meet: str
    note: Optional[str] = None
    timezone: str
    status: DateStatus
    last_updated_by: str
    created_at: datetime
    updated_at: datetime

class VibeDateRespondRequest(BaseModel):
    action: DateStatus # accepted, rejected, proposed_changes
    where: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    how_we_meet: Optional[str] = None
    note: Optional[str] = None

class VibeDateListResponse(BaseModel):
    success: bool
    data: List[VibeDateResponse]
    total: int
    page: int
    size: int
    timezone: str
