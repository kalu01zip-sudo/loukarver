from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, Dict, Any

EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

class SignupRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="User's email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")

class VerifyEmailRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

class ResendOtpRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered email address")

class SigninRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered email address")
    password: str = Field(..., description="Account password")

class OAuthRequest(BaseModel):
    token: str = Field(..., description="OAuth identity token from provider")

class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered email address")

class ResetPasswordRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserMeResponse(BaseModel):
    id: str = Field(..., validation_alias=AliasChoices("id", "_id"))
    email: Optional[str] = None
    name: Optional[str] = None
    is_verified: bool = False
    is_aligned: bool = False
    partner: Optional[Dict[str, Any]] = None
    secret_key: Optional[str] = None

    model_config = {
        "populate_by_name": True
    }
