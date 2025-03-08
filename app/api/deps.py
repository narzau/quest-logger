# app/api/deps.py
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core import security
from app.core.config import settings
from app.db.base import SessionLocal
from app.services.quest_service import QuestService
from app.services.user_service import UserService
from app.services.achievement_service import AchievementService
from app.services.google_calendar_service import GoogleCalendarService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """
    Provides a UserService instance with DB session.
    """
    return UserService(db)


def get_quest_service(db: Session = Depends(get_db)) -> QuestService:
    """
    Provides a QuestService instance with DB session.
    """
    return QuestService(db)


def get_achievement_service(db: Session = Depends(get_db)) -> AchievementService:
    """
    Provides a AchievementService instance with DB session.
    """
    return AchievementService(db)


def get_calendar_service(db: Session = Depends(get_db)) -> GoogleCalendarService:
    """
    Provides a GoogleCalendarService instance with DB session.
    """
    return GoogleCalendarService(db)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> models.User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = user_service.get_user_by_id(token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
