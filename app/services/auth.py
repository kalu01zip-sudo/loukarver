import random
import string
import hashlib
import secrets
import jwt
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.schemas.auth import (
    SignupRequest, VerifyEmailRequest, ResendOtpRequest,
    SigninRequest, OAuthRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest
)
from app.services.relationships import relationship_service

# JWT configuration algorithm
JWT_ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_val = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return f"{salt}${hash_val}"

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt, hash_val = hashed_password.split("$")
        check_val = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return secrets.compare_digest(hash_val, check_val)
    except Exception:
        return False

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_token(token: str, secret: Optional[str] = None) -> Optional[dict]:
    try:
        if secret:
            return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        # Try access token key, fallback to refresh token key
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            return jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

def send_otp_email(to_email: str, otp: str, subject: str = "Verify your email - Loukarver") -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[SMTP Warning] Credentials missing in .env, skipping email to {to_email}. OTP is {otp}")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Loukarver <{settings.FROM_EMAIL or settings.SMTP_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <h2 style="color: #6c5ce7; text-align: center; margin-bottom: 24px;">Loukarver</h2>
                <p>Hello,</p>
                <p>Please use the following One-Time Password (OTP) to complete your verification or request:</p>
                <div style="font-size: 32px; font-weight: bold; text-align: center; margin: 30px 0; letter-spacing: 4px; color: #2d3436; background: #f1f2f6; padding: 15px; border-radius: 6px;">
                    {otp}
                </div>
                <p style="font-size: 13px; color: #7f8c8d; text-align: center; margin-top: 30px;">
                    This code is valid for 15 minutes. If you did not request this code, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))
        
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        server.quit()
        print(f"[SMTP Success] Sent email to {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP Error] Failed to send email to {to_email}: {e}. Falling back to stdout. OTP is {otp}")
        return False

class AuthService:
    def __init__(self) -> None:
        self.collection = relationship_service.collection

    async def signup(self, payload: SignupRequest) -> Dict[str, Any]:
        email = payload.email.lower()
        
        # Check existing user
        existing = await self.collection.find_one({"email": email})
        if existing:
            raise ValueError("Email already registered")
            
        password_hash = hash_password(payload.password)
        # Generate 6-digit OTP
        otp = "".join(random.choices(string.digits, k=6))
        
        # Generate unique secret key for relationship
        secret_key = await relationship_service.generate_unique_secret_key()
        
        new_user = {
            "email": email,
            "password_hash": password_hash,
            "name": email.split("@")[0],
            "is_verified": False,
            "otp": otp,
            "is_aligned": False,
            "partner": None,
            "secret_key": secret_key,
            "city_name": "",
            "relationship_start_date": "",
            "is_long_distance": False
        }
        
        result = await self.collection.insert_one(new_user)
        new_user["id"] = str(result.inserted_id)
        
        # Deliver SMTP verification email
        send_otp_email(email, otp, subject="Verify your email - Loukarver")
        
        return new_user

    async def verify_email(self, payload: VerifyEmailRequest) -> Dict[str, Any]:
        email = payload.email.lower()
        user = await self.collection.find_one({"email": email})
        if not user:
            raise ValueError("User not found")
            
        if user.get("is_verified"):
            raise ValueError("Email already verified")
            
        if user.get("otp") != payload.otp:
            raise ValueError("Invalid OTP code")
            
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_verified": True}, "$unset": {"otp": ""}}
        )
        
        # Generate tokens for immediate sign-in
        token_data = {"user_id": str(user["_id"]), "email": email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def resend_otp(self, payload: ResendOtpRequest) -> bool:
        email = payload.email.lower()
        user = await self.collection.find_one({"email": email})
        if not user:
            raise ValueError("User not found")
            
        if user.get("is_verified"):
            raise ValueError("Email already verified")
            
        otp = "".join(random.choices(string.digits, k=6))
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"otp": otp}}
        )
        
        # Resend SMTP email
        send_otp_email(email, otp, subject="Resend verification email - Loukarver")
        return True

    async def signin(self, payload: SigninRequest) -> Dict[str, Any]:
        email = payload.email.lower()
        user = await self.collection.find_one({"email": email})
        if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
            raise ValueError("Invalid email or password")
            
        if not user.get("is_verified"):
            raise PermissionError("Email not verified")
            
        # Generate tokens
        token_data = {"user_id": str(user["_id"]), "email": email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        user["id"] = str(user["_id"])
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user
        }

    async def oauth_signin(self, provider: str, token: str) -> Dict[str, Any]:
        import httpx
        
        email = None
        name = "Google User"
        
        if provider == "google":
            # Verify the Google ID Token
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise ValueError("Invalid Google token")
                payload = resp.json()
                email = payload.get("email", "").lower()
                name = payload.get("name", email.split("@")[0].capitalize())
                
                if not email:
                    raise ValueError("No email found in Google token")
        else:
            # For Apple or mocked logic
            import re
            if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", token):
                email = token.lower()
                name = email.split("@")[0].capitalize()
            else:
                raise ValueError("Invalid mocked token or unsupported provider")

        user = await self.collection.find_one({"email": email})
        if not user:
            # Auto-signup verified OAuth user
            secret_key = await relationship_service.generate_unique_secret_key()
            user = {
                "email": email,
                "password_hash": None,
                "name": name,
                "is_verified": True,
                "is_aligned": False,
                "partner": None,
                "secret_key": secret_key,
                "city_name": "",
                "relationship_start_date": "",
                "is_long_distance": False
            }
            result = await self.collection.insert_one(user)
            user["id"] = str(result.inserted_id)
        else:
            user["id"] = str(user["_id"])
            if not user.get("is_verified"):
                await self.collection.update_one({"_id": user["_id"]}, {"$set": {"is_verified": True}})
                user["is_verified"] = True
                
        token_data = {"user_id": user["id"], "email": email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user
        }

    async def refresh(self, payload: RefreshRequest) -> str:
        # Pins refresh token validation to settings.REFRESH_SECRET_KEY
        token_payload = decode_token(payload.refresh_token, secret=settings.REFRESH_SECRET_KEY)
        if not token_payload or token_payload.get("type") != "refresh":
            raise ValueError("Invalid or expired refresh token")
            
        user_id = token_payload.get("user_id")
        email = token_payload.get("email")
        
        from bson import ObjectId
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found")
            
        return create_access_token({"user_id": user_id, "email": email})

    async def forgot_password(self, payload: ForgotPasswordRequest) -> bool:
        email = payload.email.lower()
        user = await self.collection.find_one({"email": email})
        if not user:
            raise ValueError("User not found")
            
        otp = "".join(random.choices(string.digits, k=6))
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"otp": otp}}
        )
        
        # Deliver password reset OTP email
        send_otp_email(email, otp, subject="Password Reset Request - Loukarver")
        return True

    async def reset_password(self, payload: ResetPasswordRequest) -> bool:
        email = payload.email.lower()
        user = await self.collection.find_one({"email": email})
        if not user:
            raise ValueError("User not found")
            
        if user.get("otp") != payload.otp:
            raise ValueError("Invalid OTP code")
            
        password_hash = hash_password(payload.new_password)
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"password_hash": password_hash}, "$unset": {"otp": ""}}
        )
        return True

    async def change_password(self, user_id: str, payload: ChangePasswordRequest) -> bool:
        from bson import ObjectId
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found")
            
        if not user.get("password_hash") or not verify_password(payload.old_password, user["password_hash"]):
            raise ValueError("Invalid old password")
            
        password_hash = hash_password(payload.new_password)
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"password_hash": password_hash}}
        )
        return True

    async def delete_user(self, user_id: str) -> bool:
        from bson import ObjectId
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

auth_service = AuthService()
