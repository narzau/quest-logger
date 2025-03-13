# app/api/deps.py
from typing import Generator, Optional, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core import security
from app.core.config import settings
from app.db.base import SessionLocal
from app.db.session import get_db
from app.models.user import User
from app.services.quest_service import QuestService
from app.services.user_service import UserService
from app.services.achievement_service import AchievementService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.subscription_service import SubscriptionService
from app.services.note_service import NoteService
from app.utils.dependencies import get_service, cached_service


# OAuth2 password bearer scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


# Service dependencies - defined as functions that will be called at runtime
# These will only be evaluated after services have been registered
def get_note_service():
    return get_service(NoteService)


def get_quest_service():
    return get_service(QuestService)


def get_subscription_service():
    return get_service(SubscriptionService)


def get_user_service():
    return get_service(UserService)


# Cached version
def get_cached_user_service():
    return cached_service(UserService)


# Authentication dependencies
async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service()),
) -> User:
    """
    Get the current authenticated user.

    Args:
        db: Database session
        token: JWT token from the request
        user_service: Injected user service

    Returns:
        Authenticated user object

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Verify the token and extract the subject (user id)
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id: int = int(payload["sub"])
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use the injected user service
    user = user_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current authenticated and active user.

    Args:
        current_user: Authenticated user object

    Returns:
        Authenticated and active user object

    Raises:
        HTTPException: If the user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


def get_achievement_service():
    """
    Get dependency for AchievementService.
    """
    return get_service(AchievementService)


def get_calendar_service():
    """
    Get dependency for GoogleCalendarService.
    """
    return get_service(GoogleCalendarService)
