# app/schemas/token.py
from typing import Optional, Dict, Any

from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    username: Optional[str] = None
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo
    subscription: Optional[Dict[str, Any]] = None


class TokenPayload(BaseModel):
    sub: Optional[int] = None
