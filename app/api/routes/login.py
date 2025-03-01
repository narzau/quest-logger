# app/api/endpoints/login.py
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import deps
from app.core import security
from app.core.config import settings

router = APIRouter()


@router.post("/access-token", response_model=schemas.Token)
def login_access_token(
    *, db: Session = Depends(deps.get_db), login_input: schemas.UserLogin
) -> Any:
    """
    Login with email/username and password, get an access token for future requests
    """
    # Try to find user by email
    user = (
        db.query(models.User).filter(models.User.email == login_input.username).first()
    )

    # If not found by email, try username
    if not user:
        user = (
            db.query(models.User)
            .filter(models.User.username == login_input.username)
            .first()
        )

    # Validate credentials
    if not user or not security.verify_password(
        login_input.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=400, detail="Incorrect email/username or password"
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
            # Add any other user details you want to return
        },
    }
