from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    hospital_id: str
    full_name: str
    role: str
    expires_at: datetime


class RegisterRequest(BaseModel):
    """User registration request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)
    hospital_id: str
    role: str = "doctor"
    department: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema."""
    user_id: str
    email: str
    full_name: str
    role: str
    department: Optional[str]
    hospital_id: str
    is_active: bool
    created_at: datetime


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: str  # user_id
    hospital_id: str
    role: str
    exp: datetime
    iat: datetime


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    current_password: str
    new_password: str = Field(..., min_length=8)
