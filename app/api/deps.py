# app/api/deps.py
import datetime

from fastapi import Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings
from app.core.constants import SubscriptionStatus as SubscriptionStatusEnum
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import SubscriptionStatus, SubscriptionUpdate
from app.services.note_service import NoteService
from app.services.quest_service import QuestService
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.services.achievement_service import AchievementService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.progression_service import ProgressionService
from app.utils.dependencies import get_service, cached_service
from app.utils.audio_utils import get_audio_info

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


def get_achievement_service():
    return get_service(AchievementService)


def get_calendar_service():
    return get_service(GoogleCalendarService)

def get_progression_service():
    return get_service(ProgressionService)

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

async def validate_active_subscription(
    current_user: User = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service()),
) -> SubscriptionStatus:
    """
    Get and verify the user has an active subscription.
    
    Args:
        current_user: Authenticated user object
        subscription_service: Subscription service

    Returns:
        User's subscription status
        
    Raises:
        HTTPException: If the user doesn't have an active subscription
    """
    # Get the user's current subscription status
    subscription_status = await subscription_service.get_subscription_status(current_user.id)
    
    # Real-time check if subscription has expired (even if not yet updated by background task)
    if subscription_status.status == SubscriptionStatusEnum.ACTIVE and subscription_status.current_period_end:
        if subscription_status.current_period_end < datetime.datetime.utcnow():
            # Subscription has expired but hasn't been updated by background task yet
            # Update it now and get fresh status
            subscription = subscription_service.repository.get_by_user_id(current_user.id)
            if subscription:
                update_data = SubscriptionUpdate(status=SubscriptionStatusEnum.PAST_DUE)
                subscription_service.repository.update_subscription(subscription, update_data)
                # Re-fetch status with updated information
                subscription_status = await subscription_service.get_subscription_status(current_user.id)
    
    # Check if the subscription is active or if it's canceled but still within the current period
    is_active_status = subscription_status.status in [SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]
    is_canceled_with_remaining_time = (
        subscription_status.status == SubscriptionStatusEnum.CANCELED and 
        subscription_status.current_period_end and 
        subscription_status.current_period_end > datetime.datetime.utcnow()
    )
    
    if not (is_active_status or is_canceled_with_remaining_time):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required for this feature"
        )
    
    return subscription_status

async def validate_available_recording_time(
    audio_file: UploadFile = File(...),
    subscription_service: SubscriptionService = Depends(get_subscription_service()),
    current_user: User = Depends(get_current_active_user),
) -> float:
    # validate the user has recording time left, even though they have an active subscription (or canceled with remaining time)
    subscription_status = await subscription_service.get_subscription_status(current_user.id)
    audio_info = await get_audio_info(audio_file)
    audio_duration: float = audio_info["duration"]
    audio_duration_minutes = audio_duration / 60        
    if (
        subscription_status.minutes_used + audio_duration_minutes
        > subscription_status.minutes_limit
    ):
        remaining = max(0, subscription_status.minutes_limit - subscription_status.minutes_used)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have reached your monthly recording limit. You have {remaining:.1f} minutes remaining of your {subscription_status.minutes_limit} minute limit."
        )

async def validate_audio_gen_access(
    subscription_status: SubscriptionStatus = Depends(validate_active_subscription), # validate subscription access
    validate_available_recording_time: float = Depends(validate_available_recording_time), # validate recording time left
) -> tuple[SubscriptionStatus, float]:
    return subscription_status, validate_available_recording_time