from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SecretRead(BaseModel):
    id: str
    sender_id: str
    filename: str
    file_type: str
    size: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    delete_after: Optional[str] = None
    prevent_screenshot: bool = True
    user_name: str
    partner_name: str

class SecretPaginatedResponse(BaseModel):
    success: bool
    data: List[SecretRead]
    total: int
    page: int
    size: int

class SecretPatchScreenshot(BaseModel):
    prevent_screenshot: bool

class GenericResponse(BaseModel):
    success: bool
    message: str
