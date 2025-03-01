# app/schemas/user.py
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    is_active: Optional[bool] = True


class UserLogin(BaseModel):
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., min_length=6, description="User password")


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    username: str
    password: str


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None


class UserInDBBase(UserBase):
    id: Optional[int] = None
    level: int = 1
    experience: int = 0

    class Config:
        from_attributes = True


# Additional properties to return via API
class User(UserInDBBase):
    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str
