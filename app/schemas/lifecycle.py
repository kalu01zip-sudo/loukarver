from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date
import re

class PeriodCreate(BaseModel):
    start_date: str = Field(..., description="Start date of the period in mm.dd.yyyy format", examples=["06.01.2026"])

    @field_validator("start_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{2}[\.,]\d{2}[\.,]\d{4}$", v):
            raise ValueError("Date must be in mm.dd.yyyy or mm.dd,yyyy format")
        parts = re.split(r"[\.,]", v)
        try:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            date(year, month, day)
        except ValueError:
            raise ValueError("Invalid calendar date. Expected mm.dd.yyyy")
        return v

class PeriodUpdate(BaseModel):
    start_date: str = Field(..., description="Updated start date in mm.dd.yyyy format")

    @field_validator("start_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{2}[\.,]\d{2}[\.,]\d{4}$", v):
            raise ValueError("Date must be in mm.dd.yyyy or mm.dd,yyyy format")
        return v

class PeriodResponseData(BaseModel):
    id: str
    user_id: str
    start_date: str

class PhaseNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, examples=["Feeling a bit tired today."])
    timezone: str = Field("UTC", description="Client's IANA timezone for date resolution", examples=["Asia/Dhaka"])

class PhaseNoteUpdate(BaseModel):
    text: str = Field(..., min_length=1)

class PhaseNoteResponseData(BaseModel):
    id: str
    user_id: str
    date: str
    text: str
    created_ago: str
    is_owner: bool

class LifeCycleStats(BaseModel):
    current_phase: str # Menstrual, Follicular, Ovulatory, Luteal
    days_since_start: int
    cycle_length_used: int
    next_period_date: str
    days_until_next_period: int
    phase_description: str

class LifeCycleResponse(BaseModel):
    success: bool
    message: str
    period_user_name: Optional[str] = None
    stats: Optional[LifeCycleStats] = None
    recent_history: List[PeriodResponseData] = []
    current_note: Optional[PhaseNoteResponseData] = None
