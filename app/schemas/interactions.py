from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InteractionState(BaseModel):
    partner_name: str
    count: int
    last_activity: Optional[datetime] = None

class InteractionResponse(BaseModel):
    success: bool
    data: InteractionState

class GenericResponse(BaseModel):
    success: bool
    message: str
