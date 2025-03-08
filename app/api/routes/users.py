# app/api/endpoints/users.py
from typing import Any, List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.user_service import UserService
from app.api import deps
from app.core.exceptions import DuplicateResourceException, BusinessException

router = APIRouter()


@router.post("/", response_model=schemas.User)
def create_user(
    *,
    user_in: schemas.UserCreate,
    user_service: UserService = Depends(deps.get_user_service),
) -> Any:
    """
    Create new user.
    """
    try:
        return user_service.create_user(user_in)
    except DuplicateResourceException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except BusinessException as e:
        # Generic business rule violation
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=schemas.User)
def read_user_me(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


@router.put("/me", response_model=schemas.User)
def update_user_me(
    *,
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
    user_service: UserService = Depends(deps.get_user_service),
) -> Any:
    """
    Update own user.
    """

    try:
        return user_service.update(current_user.id, user_in)
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))
