from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class IdeaBase(BaseModel):
    name: str
    time: str
    tagline: str
    category: str

class IdeaCreate(IdeaBase):
    pass

class IdeaUpdate(BaseModel):
    name: Optional[str] = None
    time: Optional[str] = None
    tagline: Optional[str] = None
    category: Optional[str] = None

class IdeaRead(IdeaBase):
    id: str
    is_personalized: bool = False
    user_id: Optional[str] = None

class IdeaProgressRead(BaseModel):
    id: str
    idea_id: str
    name: str
    time: str
    tagline: str
    category: str
    # Acceptance
    is_accepted_user: bool = False
    is_accepted_partner: bool = False
    accepted_at_user: Optional[datetime] = None
    accepted_at_partner: Optional[datetime] = None
    # Countdown
    countdown_start: Optional[datetime] = None
    countdown_end: Optional[datetime] = None
    # Completion
    is_done_user: bool = False
    is_done_partner: bool = False
    done_at_user: Optional[datetime] = None
    done_at_partner: Optional[datetime] = None
    completed_in_user: Optional[str] = None
    completed_in_partner: Optional[str] = None
    # Meta
    user_name: str
    partner_name: str
    created_at: datetime
    is_completed: bool = False
    is_expired: bool = False

class IdeaListResponse(BaseModel):
    success: bool
    data: List[IdeaRead]
    total: int
    page: int
    size: int

class IdeaProgressPaginatedResponse(BaseModel):
    success: bool
    data: List[IdeaProgressRead]
    total: int
    page: int
    size: int

class IdeaProgressResponse(BaseModel):
    success: bool
    data: IdeaProgressRead

class CategoryListResponse(BaseModel):
    success: bool
    data: List[str]

class GenericResponse(BaseModel):
    success: bool
    message: str
