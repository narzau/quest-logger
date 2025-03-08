# app/api/endpoints/login.py
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app import schemas
from app.services.user_service import UserService
from app.api import deps
from app.core import security
from app.core.config import settings

router = APIRouter()


@router.post("/access-token", response_model=schemas.Token)
def login_access_token(
    *,
    login_input: schemas.UserLogin,
    user_service: UserService = Depends(deps.get_user_service)
) -> Any:
    """
    Login with email/username and password, get an access token for future requests
    """

    user = user_service.get_user_by_email(login_input.email)

    # Validate credentials
    if not user or not security.verify_password(
        login_input.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=400, detail="Incorrect email or password"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }
