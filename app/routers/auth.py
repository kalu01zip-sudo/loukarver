from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import (
    SignupRequest, VerifyEmailRequest, ResendOtpRequest,
    SigninRequest, OAuthRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
    TokenResponse, UserMeResponse
)
from app.services.auth import auth_service, decode_token
from app.services.relationships import relationship_service

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identifier"
        )
    from bson import ObjectId
    try:
        user = await relationship_service.collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    user["id"] = str(user["_id"])
    return user

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):
    """Registers a new user account and triggers an email verification OTP code."""
    try:
        await auth_service.signup(payload)
        return {
            "success": True,
            "message": "Signup successful! Verification OTP code has been sent to your email."
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during signup: {str(e)}"
        )

@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(payload: VerifyEmailRequest):
    """Verifies a user email using the 6-digit OTP code received during signup."""
    try:
        return await auth_service.verify_email(payload)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/resend-otp")
async def resend_otp(payload: ResendOtpRequest):
    """Resends a new 6-digit OTP code to the registered email address."""
    try:
        await auth_service.resend_otp(payload)
        return {
            "success": True,
            "message": "A new verification OTP code has been sent to your email."
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/signin", response_model=TokenResponse)
async def signin(payload: SigninRequest):
    """Authenticates email and password credentials, returning authorization JWTs."""
    try:
        result = await auth_service.signin(payload)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"]
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/google", response_model=TokenResponse)
async def google_signin(payload: OAuthRequest):
    """Mocks Google OAuth Sign-in, returning authorization tokens."""
    try:
        result = await auth_service.oauth_signin("google", payload.token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google sign-in error: {str(e)}"
        )

@router.post("/apple", response_model=TokenResponse)
async def apple_signin(payload: OAuthRequest):
    """Mocks Apple Sign-in, returning authorization tokens."""
    try:
        result = await auth_service.oauth_signin("apple", payload.token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Apple sign-in error: {str(e)}"
        )

@router.post("/refresh")
async def refresh(payload: RefreshRequest):
    """Refreshes and issues a new access token using a valid refresh token."""
    try:
        new_access = await auth_service.refresh(payload)
        return {
            "access_token": new_access,
            "token_type": "bearer"
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/signout")
async def signout(current_user: dict = Depends(get_current_user)):
    """Simulates signing out by validating authorization headers."""
    return {
        "success": True,
        "message": f"Successfully signed out user {current_user['email']}."
    }

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Triggers password reset flow, generating a new password reset OTP code."""
    try:
        await auth_service.forgot_password(payload)
        return {
            "success": True,
            "message": "If the email exists, a password reset OTP code has been sent."
        }
    except ValueError as ve:
        # Avoid user enumeration by returning a success message even if not found
        return {
            "success": True,
            "message": "If the email exists, a password reset OTP code has been sent."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Resets the account password using the password reset OTP code."""
    try:
        await auth_service.reset_password(payload)
        return {
            "success": True,
            "message": "Password reset successfully! You can now login with your new password."
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Allows authenticated users to change their account password."""
    try:
        await auth_service.change_password(current_user["id"], payload)
        return {
            "success": True,
            "message": "Password changed successfully!"
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/me", response_model=UserMeResponse, response_model_exclude_none=True)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Retrieves current authenticated user's profile and relationship alignment details."""
    # Use the alignment status and partner info already stored in the user document
    # which is fetched by get_current_user.
    
    # If is_aligned is True in the user document, we trust it.
    # The partner info is also already in the user document.
    
    # We can keep the vibe_pulse check as a fallback or for additional metadata if needed,
    # but the primary source of truth for /users/aligned is the user document.
    
    return current_user

@router.delete("/me")
async def delete_me(current_user: dict = Depends(get_current_user)):
    """Deletes current authenticated user's account from the database."""
    try:
        await auth_service.delete_user(current_user["id"])
        return {
            "success": True,
            "message": "Account successfully deleted."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during account deletion: {str(e)}"
        )
