import logging
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import get_current_user, validate_active_subscription
from app.models import User
from app.services.time_tracking_service import TimeTrackingService
from app.schemas.time_tracking import (
    TimeEntry,
    TimeEntryCreate,
    TimeEntryUpdate,
    TimeEntryList,
    SessionStart,
    TimeTrackingSettings,
    TimeTrackingSettingsUpdate,
    TimeTrackingStats,
)
from app.core.logging import log_context
from app.core.exceptions import BusinessException, ResourceNotFoundException
from app.utils.dependencies import get_service
from app.schemas.subscription import SubscriptionStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# Time Entry CRUD endpoints

@router.get("/entries", response_model=TimeEntryList)
async def list_time_entries(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    payment_status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntryList:
    """Get a list of time entries with pagination and filtering"""
    with log_context(
        user_id=current_user.id,
        action="list_time_entries",
        start_date=start_date,
        end_date=end_date,
        payment_status=payment_status,
    ):
        try:
            return await time_tracking_service.get_time_entries(
                user_id=current_user.id,
                skip=skip,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
                payment_status=payment_status,
            )
        except BusinessException as e:
            logger.warning(f"Business error listing time entries: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/entries/{entry_id}", response_model=TimeEntry)
async def get_time_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntry:
    """Get a specific time entry by ID"""
    with log_context(user_id=current_user.id, action="get_time_entry", entry_id=entry_id):
        try:
            return await time_tracking_service.get_time_entry(current_user.id, entry_id)
        except ResourceNotFoundException as e:
            logger.warning(f"Time entry {entry_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail=str(e))


@router.post("/entries", response_model=TimeEntry)
async def create_time_entry(
    data: TimeEntryCreate,
    subscription_status: SubscriptionStatus = Depends(validate_active_subscription),
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntry:
    """Create a new time entry - requires active subscription"""
    with log_context(user_id=current_user.id, action="create_time_entry"):
        try:
            logger.info(f"Creating time entry for user {current_user.id}")
            return await time_tracking_service.create_time_entry(current_user.id, data)
        except BusinessException as e:
            logger.warning(f"Business error creating time entry: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.put("/entries/{entry_id}", response_model=TimeEntry)
async def update_time_entry(
    entry_id: int,
    data: TimeEntryUpdate,
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntry:
    """Update an existing time entry"""
    with log_context(
        user_id=current_user.id, action="update_time_entry", entry_id=entry_id
    ):
        try:
            return await time_tracking_service.update_time_entry(
                current_user.id, entry_id, data
            )
        except ResourceNotFoundException as e:
            logger.warning(f"Time entry {entry_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail=str(e))
        except BusinessException as e:
            logger.warning(f"Business error updating time entry: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_time_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> Response:
    """Delete a time entry"""
    with log_context(
        user_id=current_user.id, action="delete_time_entry", entry_id=entry_id
    ):
        try:
            await time_tracking_service.delete_time_entry(current_user.id, entry_id)
            return Response(status_code=204)
        except ResourceNotFoundException as e:
            logger.warning(f"Time entry {entry_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail=str(e))


# Session management endpoints

@router.post("/sessions/start", response_model=TimeEntry)
async def start_session(
    data: SessionStart,
    subscription_status: SubscriptionStatus = Depends(validate_active_subscription),
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntry:
    """Start a new time tracking session - requires active subscription"""
    with log_context(user_id=current_user.id, action="start_session"):
        try:
            logger.info(f"Starting session for user {current_user.id}")
            return await time_tracking_service.start_session(current_user.id, data)
        except HTTPException:
            raise  # Re-raise HTTPExceptions as-is
        except BusinessException as e:
            logger.warning(f"Business error starting session: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{entry_id}/stop", response_model=TimeEntry)
async def stop_session(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeEntry:
    """Stop an active time tracking session"""
    with log_context(
        user_id=current_user.id, action="stop_session", entry_id=entry_id
    ):
        try:
            return await time_tracking_service.stop_session(current_user.id, entry_id)
        except ResourceNotFoundException as e:
            logger.warning(f"Time entry {entry_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail=str(e))
        except BusinessException as e:
            logger.warning(f"Business error stopping session: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/active", response_model=Optional[TimeEntry])
async def get_active_session(
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> Optional[TimeEntry]:
    """Get the current active time tracking session"""
    with log_context(user_id=current_user.id, action="get_active_session"):
        return await time_tracking_service.get_active_session(current_user.id)


# Statistics endpoint

@router.get("/stats", response_model=TimeTrackingStats)
async def get_statistics(
    period: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeTrackingStats:
    """Get time tracking statistics"""
    with log_context(user_id=current_user.id, action="get_statistics", period=period):
        return await time_tracking_service.get_statistics(current_user.id, period)


# Settings endpoints

@router.get("/settings", response_model=TimeTrackingSettings)
async def get_settings(
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeTrackingSettings:
    """Get time tracking settings"""
    with log_context(user_id=current_user.id, action="get_settings"):
        return await time_tracking_service.get_settings(current_user.id)


@router.put("/settings", response_model=TimeTrackingSettings)
async def update_settings(
    data: TimeTrackingSettingsUpdate,
    current_user: User = Depends(get_current_user),
    time_tracking_service: TimeTrackingService = Depends(get_service(TimeTrackingService)),
) -> TimeTrackingSettings:
    """Update time tracking settings"""
    with log_context(user_id=current_user.id, action="update_settings"):
        logger.info(f"Updating settings for user {current_user.id}")
        return await time_tracking_service.update_settings(current_user.id, data) 