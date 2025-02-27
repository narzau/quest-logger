# app/api/endpoints/achievements.py
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import deps

router = APIRouter()


@router.get("/", response_model=List[schemas.UserAchievement])
def read_user_achievements(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve user's unlocked achievements.
    """
    user_achievements = (
        db.query(models.UserAchievement)
        .filter(models.UserAchievement.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return user_achievements


@router.get("/available", response_model=List[schemas.Achievement])
def read_all_achievements(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve all available achievements.
    """
    achievements = db.query(models.Achievement).all()
    return achievements