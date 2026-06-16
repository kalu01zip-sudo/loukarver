from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MilestoneStep(BaseModel):
    id: str
    text: str
    is_completed: bool = False
    completed_by: Optional[str] = None
    completed_by_name: Optional[str] = None
    completed_at: Optional[datetime] = None

class MilestoneStepCreate(BaseModel):
    text: str
    timezone: str = "UTC"

class MilestoneStepUpdate(BaseModel):
    text: Optional[str] = None
    is_completed: Optional[bool] = None
    timezone: str = "UTC"

class MilestoneBase(BaseModel):
    name: str
    why_it_matters: str
    is_private: bool = False
    pin: Optional[str] = Field(None, description="4-digit PIN for private milestones")
    timezone: str = "UTC"

class MilestoneCreate(MilestoneBase):
    steps: List[MilestoneStepCreate] = []

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Our Dream Home",
                "why_it_matters": "To build a future together and have a space of our own.",
                "is_private": False,
                "pin": "1234",
                "steps": [
                    {"text": "Save for down payment"},
                    {"text": "Get pre-approved for mortgage"},
                    {"text": "Find a realtor we both like"},
                    {"text": "Visit at least 10 houses"},
                    {"text": "Make an offer!"}
                ]
            }
        }
    }

class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    why_it_matters: Optional[str] = None
    is_private: Optional[bool] = None
    pin: Optional[str] = None
    timezone: str = "UTC"

class MilestoneResponse(BaseModel):
    id: str
    creator_id: str
    partner_id: str
    name: str
    why_it_matters: str
    is_private: bool
    steps: List[MilestoneStep]
    progress: float
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    is_locked: bool = False # For private milestones without correct PIN

class MilestonePaginatedResponse(BaseModel):
    success: bool
    data: List[MilestoneResponse]
    total: int
    page: int
    size: int

class MilestoneUnlock(BaseModel):
    pin: str
    timezone: str = "UTC"

class GenericResponse(BaseModel):
    success: bool
    message: str
