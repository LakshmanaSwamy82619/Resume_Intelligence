from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp_code: str
    purpose: str = "password_reset"


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: Optional[str] = None
    reset_token: Optional[str] = None
    new_password: str = Field(min_length=8)

    @model_validator(mode="after")
    def require_reset_credential(self):
        if bool(self.otp_code) == bool(self.reset_token):
            raise ValueError("Provide exactly one of otp_code or reset_token.")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class FirstLoginPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool = False
    phone: Optional[str] = None
    profile_picture_url: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateHrAccountRequest(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    temporary_password: Optional[str] = Field(default=None, min_length=8)


class UpdateAccountStatusRequest(BaseModel):
    is_active: bool


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    notification_preferences: Optional[dict] = None
