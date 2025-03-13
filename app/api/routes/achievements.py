# app/api/endpoints/achievements.py
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException

from app import models, schemas
from app.api import deps
from app.services.achievement_service import AchievementService

router = APIRouter()


@router.get("/", response_model=List[schemas.UserAchievement])
def read_user_achievements(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
    achievement_service: AchievementService = Depends(deps.get_achievement_service()),
) -> Any:
    """
    Retrieve user's unlocked achievements.
    """
    user_achievements = achievement_service.get_user_achievements(current_user.id)
    return user_achievements


@router.get("/available", response_model=List[schemas.Achievement])
def read_all_achievements(
    current_user: models.User = Depends(deps.get_current_active_user),
    achievement_service: AchievementService = Depends(deps.get_achievement_service()),
) -> Any:
    """
    Retrieve all available achievements.
    """
    achievements = achievement_service.get_all()
    return achievements
