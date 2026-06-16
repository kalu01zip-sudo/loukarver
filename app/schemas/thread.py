from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime
from enum import Enum

class ThreadCategory(str, Enum):
    LETTER = "Letter"
    VOICE = "Voice"
    PHOTO = "Photo"
    PROMPT = "Prompt"
    APPRECIATION = "Appreciation"
    CHECKIN = "Checkin"

class PromptType(str, Enum):
    ROMANTIC = "Romantic"
    DESIRED = "Desired"

class PromptQuestion(BaseModel):
    id: Optional[str] = None
    category: str  # e.g., "Emotional", "Desire", "Growth", "Depth", "Memory", "Future", "Adventure", "Intense", "Daring", "Vulnerable", "Intimate"
    rating: str    # e.g., "●●○○○"
    text: str
    type: PromptType
    creator_id: Optional[str] = None # None for default global questions

class PromptQuestionCreate(BaseModel):
    category: str
    rating: str
    text: str
    type: PromptType

class ThreadMessageBase(BaseModel):
    category: ThreadCategory
    timezone: str = "UTC"

class LetterCreate(ThreadMessageBase):
    text: str

class VoiceCreate(ThreadMessageBase):
    pass # File handled via UploadFile

class PhotoCreate(ThreadMessageBase):
    caption: str

class PromptAskCreate(ThreadMessageBase):
    prompt_type: PromptType
    question_text: str
    type: str

class PromptReplyUpdate(BaseModel):
    answer: str
    timezone: str = "UTC"

class AppreciationCreate(ThreadMessageBase):
    text: str

class CheckInThreadCreate(ThreadMessageBase):
    answer_1: str
    answer_2: str
    answer_3: str
    date: str # mm.dd.yyyy

class LetterUpdate(BaseModel):
    text: Optional[str] = None
    timezone: str = "UTC"

class VoiceUpdate(BaseModel):
    timezone: str = "UTC"

class PhotoUpdate(BaseModel):
    caption: Optional[str] = None
    timezone: str = "UTC"

class PromptAskUpdate(BaseModel):
    prompt_type: Optional[PromptType] = None
    question_text: Optional[str] = None
    type: Optional[str] = None
    timezone: str = "UTC"

class AppreciationUpdate(BaseModel):
    text: Optional[str] = None
    timezone: str = "UTC"

class CheckInThreadUpdate(BaseModel):
    answer_1: Optional[str] = None
    answer_2: Optional[str] = None
    answer_3: Optional[str] = None
    date: Optional[str] = None
    timezone: str = "UTC"

class ThreadMessageResponse(BaseModel):
    id: str
    category: ThreadCategory
    sender_id: str
    sender_name: str
    user_name: str
    partner_name: str
    content: dict
    created_at: datetime
    is_sent: bool = True
    is_delivered: bool = False
    is_seen: bool = False
    
class ThreadCategoryResponse(BaseModel):
    success: bool
    data: List[str]

class GenericResponse(BaseModel):
    success: bool
    message: str
