from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class VibeQuestion(BaseModel):
    id: str
    text: str
    option_a: str
    option_b: str
    category: Optional[str] = "General"

class VibeAnswer(BaseModel):
    question_id: str
    selected_option: str # "A" or "B"

class VibeCardDaily(BaseModel):
    date: str # mm.dd.yyyy
    questions: List[VibeQuestion]

class VibeAnswerSubmit(BaseModel):
    answers: List[VibeAnswer]
    timezone: str = "UTC"

    model_config = {
        "json_schema_extra": {
            "example": {
                "answers": [
                    {"question_id": "q1_id", "selected_option": "A"},
                    {"question_id": "q2_id", "selected_option": "B"},
                    {"question_id": "q3_id", "selected_option": "A"}
                ],
                "timezone": "Asia/Dhaka"
            }
        }
    }

class VibeMatchedAnswer(BaseModel):
    question: str
    option_a: str
    option_b: str
    my_selected_option: str  # "A" or "B"
    partner_selected_option: str  # "A" or "B"
    my_answer: str
    partner_answer: str
    is_match: bool

class VibeMatchResult(BaseModel):
    user_name: str
    partner_name: str
    daily_match_percent: float
    cumulative_match_percent: float
    matched_answers: List[VibeMatchedAnswer]

class VibeMultiMatchResult(BaseModel):
    success: bool
    data: List[VibeMatchResult]

class VibeStreakResponse(BaseModel):
    current_streak: int
    last_answered: Optional[datetime] = None
    is_answered_today: bool

class GenericResponse(BaseModel):
    success: bool
    message: str

# --- History System ---

class VibeHistoryEntry(BaseModel):
    date: str
    question: str
    category: Optional[str] = "General"
    option_a: str
    option_b: str
    user_name: str
    user_answer: str
    partner_name: str
    partner_answer: str
    is_match: bool

# --- Analytics / Pulse Insights ---

class CategoryMatch(BaseModel):
    category: str
    match_percentage: float
    total_questions: int
    matched_questions: int

class PulseAnalytics(BaseModel):
    partner_id: str
    partner_name: str
    cumulative_match_percent: float
    total_questions_answered: int
    matched_questions_count: int
    overall_match_percentage: float
    strongest_categories: List[CategoryMatch]
    weakest_categories: List[CategoryMatch]
    recent_matches: List[VibeHistoryEntry]
    recent_differences: List[VibeHistoryEntry]

class PulseAnalyticsResponse(BaseModel):
    success: bool
    data: List[PulseAnalytics]

class VibeHistoryPaginatedResponse(BaseModel):
    success: bool
    data: List[VibeHistoryEntry]
    total: int
    page: int
    size: int
    category: str
