import uuid
from pydantic import BaseModel, EmailStr, ConfigDict
from src.infrastructure.database.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    tenant_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: UserRole = UserRole.consultant
    tenant_id: uuid.UUID


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None