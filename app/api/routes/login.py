# app/api/endpoints/login.py
from datetime import timedelta
from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException

from app import schemas
from app.services.user_service import UserService
from app.api import deps
from app.core import security
from app.core.config import settings
from app.services.subscription_service import SubscriptionService
from app.core.logging import log_context

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/access-token", response_model=schemas.Token)
async def login_access_token(
    *,
    login_input: schemas.UserLogin,
    user_service: UserService = Depends(deps.get_user_service()),
    subscription_service: SubscriptionService = Depends(
        deps.get_subscription_service()
    ),
) -> Any:
    """
    Login with email/username and password, get an access token for future requests
    """
    with log_context(action="login_attempt", email=login_input.email):
        logger.info(f"Login attempt for email: {login_input.email}")

        user = user_service.get_user_by_email(login_input.email)

        # Validate credentials
        if not user or not security.verify_password(
            login_input.password, user.hashed_password
        ):
            logger.warning(f"Failed login attempt for email: {login_input.email}")
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        # Get subscription status
        with log_context(user_id=user.id, action="get_subscription_status"):
            logger.info(f"Retrieving subscription status for user ID: {user.id}")
            subscription_status = await subscription_service.get_subscription_status(
                user.id
            )

        logger.info(f"Successful login for user ID: {user.id}")
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
            "subscription": subscription_status,
        }
