from pydantic import BaseModel, Field
from typing import List, Optional

class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_completed_date: Optional[str]
    is_at_risk: bool

class DayBreakdown(BaseModel):
    label: str
    date: str
    completed: bool
    ritual_type: Optional[str] = None

class StreakWeeklyResponse(BaseModel):
    days: List[DayBreakdown]
    week_completion_rate: int

class StreakPartnerResponse(BaseModel):
    partner_name: str
    partner_streak: int
    partner_last_completed: Optional[str]
    combined_days_both_completed: int
