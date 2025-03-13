# app/api/endpoints/users.py
from typing import Any, Dict
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from app import models, schemas
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.api import deps
from app.core.exceptions import DuplicateResourceException, BusinessException
from app.repositories.subscription_repository import SubscriptionRepository
from app.core.logging import log_context

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=schemas.User)
async def create_user(
    *,
    user_in: schemas.UserCreate,
    user_service: UserService = Depends(deps.get_user_service()),
    subscription_service: SubscriptionService = Depends(
        deps.get_subscription_service()
    ),
) -> Any:
    """
    Create new user and initialize a trial subscription.
    """
    try:
        # Create the user
        with log_context(action="create_user", email=user_in.email):
            logger.info(f"Creating new user with email: {user_in.email}")
            user = user_service.create_user(user_in)

            # Initialize a trial subscription
            logger.info(f"Initializing trial subscription for user ID: {user.id}")
            await subscription_service.get_subscription_status(user.id)

            return user
    except DuplicateResourceException as e:
        logger.warning(f"Duplicate user creation attempt: {str(e)}")
        raise HTTPException(status_code=409, detail=str(e))
    except BusinessException as e:
        # Generic business rule violation
        logger.warning(f"Business rule violation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=schemas.User)
def read_user_me(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    with log_context(user_id=current_user.id, action="get_current_user"):
        logger.info(f"User {current_user.id} retrieving their profile")
        return current_user


@router.put("/me", response_model=schemas.User)
def update_user_me(
    *,
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
    user_service: UserService = Depends(deps.get_user_service()),
) -> Any:
    """
    Update own user.
    """
    try:
        with log_context(user_id=current_user.id, action="update_user"):
            logger.info(f"User {current_user.id} updating their profile")
            return user_service.update(current_user)
    except BusinessException as e:
        logger.warning(f"Error updating user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/onboarding", response_model=Dict[str, Any])
async def get_onboarding_info(
    current_user: models.User = Depends(deps.get_current_active_user),
    subscription_service: SubscriptionService = Depends(
        deps.get_subscription_service()
    ),
) -> Any:
    """
    Get onboarding information for new users, including trial details
    and subscription options.
    """
    with log_context(user_id=current_user.id, action="get_onboarding_info"):
        logger.info(f"User {current_user.id} retrieving onboarding information")

        # Get current subscription status
        subscription = await subscription_service.get_subscription_status(
            current_user.id
        )

        # Get pricing information
        pricing = await subscription_service.get_pricing()

        return {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
            },
            "subscription": subscription,
            "pricing": pricing,
            "onboarding_steps": [
                {
                    "id": "welcome",
                    "title": "Welcome to Quest Logger",
                    "description": "Your personal journey companion!",
                },
                {
                    "id": "trial",
                    "title": "7-Day Free Trial",
                    "description": "You're currently on a 7-day free trial with full access to all features.",
                },
                {
                    "id": "features",
                    "title": "Explore Features",
                    "description": "Discover AI-powered notes, quest tracking, and more.",
                },
                {
                    "id": "subscription",
                    "title": "Choose Your Plan",
                    "description": "Continue with a monthly or annual subscription after your trial.",
                },
            ],
        }
