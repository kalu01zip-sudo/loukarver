from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime, date
import re

class Milestone(BaseModel):
    id: str
    title: str
    date: str
    days_left: int
    description: Optional[str] = None
    type: str = "custom" # "anniversary", "days", "birthday", "custom"

class MilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, examples=["Our First Kiss"])
    date: str = Field(..., description="Date in mm.dd.yyyy format", examples=["10.15.2023"])
    description: Optional[str] = Field(None, examples=["A magical moment in Central Park"])
    type: str = Field("custom", description="Type of milestone: birthday, custom, etc.", examples=["custom"])

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{2}[\.,]\d{2}[\.,]\d{4}$", v):
            raise ValueError("Date must be in mm.dd.yyyy or mm.dd,yyyy format")
        parts = re.split(r"[\.,]", v)
        try:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            date(year, month, day)
        except ValueError:
            raise ValueError("Invalid calendar date or format. Expected mm.dd.yyyy")
        return v

class MilestoneUpdate(BaseModel):
    title: Optional[str] = Field(None, examples=["Our First Date"])
    date: Optional[str] = Field(None, description="Date in mm.dd.yyyy format", examples=["10.10.2023"])
    description: Optional[str] = Field(None, examples=["Dinner at our favorite restaurant"])
    type: Optional[str] = Field(None, examples=["custom"])

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^\d{2}[\.,]\d{2}[\.,]\d{4}$", v):
            raise ValueError("Date must be in mm.dd.yyyy or mm.dd,yyyy format")
        parts = re.split(r"[\.,]", v)
        try:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            date(year, month, day)
        except ValueError:
            raise ValueError("Invalid calendar date or format. Expected mm.dd.yyyy")
        return v

class NextMeetCreate(BaseModel):
    date: str = Field(..., description="Date in mm.dd.yyyy format", examples=["12.31.2026"])
    time: str = Field(..., description="Time in 12h format (e.g. 08:30 PM)", examples=["11:59 PM"])
    timezone: str = Field("UTC", description="IANA Timezone of the meeting location or your current location", examples=["Asia/Dhaka"])
    city_name: str = Field(..., description="City where the meeting will take place", examples=["Dhaka"])

class NextMeetUpdate(BaseModel):
    date: Optional[str] = Field(None, description="Date in mm.dd.yyyy format", examples=["01.01.2027"])
    time: Optional[str] = Field(None, description="Time in 12h format", examples=["01:00 AM"])
    timezone: Optional[str] = Field(None, description="IANA Timezone", examples=["UTC"])
    city_name: Optional[str] = Field(None, examples=["Brooklyn"])

class Countdown(BaseModel):
    days: int
    hours: int
    minutes: int
    seconds: int

class NextMeetResponseData(BaseModel):
    date: str
    time: str
    time_name: str
    city_name: str
    countdown: Countdown

class NextMeetResponse(BaseModel):
    success: bool
    message: str
    data: Optional[NextMeetResponseData] = None

class UsStatsResponse(BaseModel):
    days_passed: int
    months_passed: int
    years_passed: int
    total_days: int
    relationship_start_date: str
    next_anniversary_date: str
    days_until_anniversary: int
    upcoming_milestones: List[Milestone]

class UsResponse(BaseModel):
    success: bool
    message: str
    data: Optional[UsStatsResponse] = None
