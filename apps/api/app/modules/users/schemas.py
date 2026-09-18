"""Request/response schemas for auth and user endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name must not be blank")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=256)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=256)


class TokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: "UserOut"
    tokens: TokensResponse


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    account_role: str
    status: str
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=20)
    bio: str | None = Field(default=None, max_length=2000)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str | None
    avatar_url: str | None
    phone: str | None
    bio: str | None


class PreferencesUpdateRequest(BaseModel):
    interests: list[str] | None = Field(default=None, max_length=30)
    pace: str | None = Field(default=None, pattern="^(RELAXED|BALANCED|PACKED)$")
    budget_level: str | None = Field(default=None, pattern="^(BUDGET|MID|PREMIUM)$")
    notes: str | None = Field(default=None, max_length=2000)


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    interests: list[str]
    pace: str | None
    budget_level: str | None
    notes: str | None
