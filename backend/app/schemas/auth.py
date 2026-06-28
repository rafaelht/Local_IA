from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    email_or_nickname: str  # Can be email or nickname
    password: str


class CreateUserRequest(BaseModel):
    email: str
    nickname: Optional[str] = None
    full_name: Optional[str] = None
    password: str
    role: str = 'user'  # 'user' or 'admin'


class UpdateUserRequest(BaseModel):
    nickname: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    nickname: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool

    model_config = {
        'from_attributes': True
    }
