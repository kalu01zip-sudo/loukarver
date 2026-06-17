from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class VibeCheckProfileCreate(BaseModel):
    name: str

class VibeCheckProfileResponse(BaseModel):
    user_id: str
    name: str
    vibe_key: str
    connect: int
    active: int
    active_users: List["PartnerStats"] = []
    inactive: int
    inactive_users: List["PartnerStats"] = []
    created_at: datetime
    updated_at: datetime

class PartnerStats(BaseModel):
    name: str
    match_percentage: float
    streak_days: int

class VibeCheckConnection(BaseModel):
    user_id: str
    name: str
    connected_at: datetime

class VibeCheckRequest(BaseModel):
    request_id: str
    sender_id: str
    sender_name: str
    created_at: datetime

class VibeCheckConnectRequest(BaseModel):
    vibe_key: str

class VibeCheckRespondRequest(BaseModel):
    accept: bool

class VibeCheckConnectionsResponse(BaseModel):
    success: bool
    data: List[VibeCheckConnection]

class VibeCheckRequestsResponse(BaseModel):
    success: bool
    data: List[VibeCheckRequest]

class VibeCheckData(BaseModel):
    # This is a placeholder for future VibeCheck specific data
    success: bool
    message: str

class VibeCheckGenericResponse(BaseModel):
    success: bool
    message: str

# --- Invite System Schemas ---

class VibeInviteResponse(BaseModel):
    invite_code: str
    invite_link: str

class VibeInviteValidateResponse(BaseModel):
    valid: bool
    inviter_name: str
    inviter_profile_picture: Optional[str] = None

class VibeInviteAcceptRequest(BaseModel):
    invite_code: str

class VibeInviteAcceptResponse(BaseModel):
    success: bool
    message: str
    partner_id: str
    partner_name: str
