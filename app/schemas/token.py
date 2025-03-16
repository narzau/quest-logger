# app/schemas/token.py
from typing import Optional

from pydantic import BaseModel

from app.schemas.subscription import SubscriptionStatus


class UserInfo(BaseModel):
    id: int
    username: Optional[str] = None
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo
    subscription: SubscriptionStatus


class TokenPayload(BaseModel):
    sub: Optional[int] = None
