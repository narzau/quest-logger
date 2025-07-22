import logging
from typing import Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.repositories.time_tracking_repository import TimeEntryRepository, TimeTrackingSettingsRepository
from app.schemas.time_tracking import (
    TimeEntryCreate,
    TimeEntryUpdate,
    TimeEntry,
    TimeEntryList,
    SessionStart,
    TimeTrackingSettings,
    TimeTrackingSettingsCreate,
    TimeTrackingSettingsUpdate,
    TimeTrackingStats,
)
from app.models.time_tracking import TimeEntryPaymentStatus
from app.core.exceptions import BusinessException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class TimeTrackingService:
    """Service for time tracking operations."""

    def __init__(self, db: Session):
        self.db = db
        self.entry_repository = TimeEntryRepository(db)
        self.settings_repository = TimeTrackingSettingsRepository(db)

    # Time Entry Methods

    async def create_time_entry(self, user_id: int, data: TimeEntryCreate) -> TimeEntry:
        """Create a new time entry"""
        logger.info(f"Creating time entry for user {user_id}")
        
        # Validate that start_time is before end_time if both are provided
        if data.end_time and data.start_time >= data.end_time:
            raise BusinessException("End time must be after start time")
        
        return self.entry_repository.create_time_entry(user_id, data)

    async def get_time_entry(self, user_id: int, entry_id: int) -> TimeEntry:
        """Get a specific time entry"""
        entry = self.entry_repository.get_user_time_entry(user_id, entry_id)
        if not entry:
            logger.warning(f"Time entry {entry_id} not found for user {user_id}")
            raise ResourceNotFoundException("Time entry not found")
        return entry

    async def update_time_entry(
        self, 
        user_id: int, 
        entry_id: int, 
        data: TimeEntryUpdate
    ) -> TimeEntry:
        """Update a time entry"""
        entry = self.entry_repository.get_user_time_entry(user_id, entry_id)
        if not entry:
            logger.warning(f"Time entry {entry_id} not found for user {user_id}")
            raise ResourceNotFoundException("Time entry not found")
        
        # Validate times if provided
        start_time = data.start_time or entry.start_time
        end_time = data.end_time or entry.end_time
        
        if end_time and start_time >= end_time:
            raise BusinessException("End time must be after start time")
        
        return self.entry_repository.update_time_entry(entry, data)

    async def delete_time_entry(self, user_id: int, entry_id: int) -> None:
        """Delete a time entry"""
        entry = self.entry_repository.get_user_time_entry(user_id, entry_id)
        if not entry:
            logger.warning(f"Time entry {entry_id} not found for user {user_id}")
            raise ResourceNotFoundException("Time entry not found")
        
        self.entry_repository.delete_time_entry(entry)
        logger.info(f"Deleted time entry {entry_id} for user {user_id}")

    async def get_time_entries(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        payment_status: Optional[str] = None,
    ) -> TimeEntryList:
        """Get paginated list of time entries"""
        # Convert payment status string to enum if provided
        payment_status_enum = None
        if payment_status:
            try:
                payment_status_enum = TimeEntryPaymentStatus(payment_status)
            except ValueError:
                raise BusinessException(f"Invalid payment status: {payment_status}")
        
        result = self.entry_repository.get_user_time_entries(
            user_id=user_id,
            skip=skip,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            payment_status=payment_status_enum,
        )
        
        return TimeEntryList(**result)

    # Session Management Methods

    async def start_session(self, user_id: int, data: SessionStart) -> TimeEntry:
        """Start a new time tracking session"""
        logger.info(f"Starting time tracking session for user {user_id}")
        
        # Check if there's already an active session
        active_session = self.entry_repository.get_active_session(user_id)
        if active_session:
            raise HTTPException(
                status_code=409,
                detail="An active session already exists. Please stop it before starting a new one."
            )
        
        # Create a new time entry without end_time (active session)
        now = datetime.utcnow()
        entry_data = TimeEntryCreate(
            date=now.date(),
            start_time=now,
            hourly_rate=data.hourly_rate,
            payment_status=TimeEntryPaymentStatus.NOT_PAID,
        )
        
        return self.entry_repository.create_time_entry(user_id, entry_data)

    async def stop_session(self, user_id: int, entry_id: int) -> TimeEntry:
        """Stop an active time tracking session"""
        logger.info(f"Stopping session {entry_id} for user {user_id}")
        
        entry = self.entry_repository.get_user_time_entry(user_id, entry_id)
        if not entry:
            raise ResourceNotFoundException("Time entry not found")
        
        if entry.end_time:
            raise BusinessException("This session has already been stopped")
        
        return self.entry_repository.stop_session(entry, datetime.utcnow())

    async def get_active_session(self, user_id: int) -> Optional[TimeEntry]:
        """Get the current active session if any"""
        return self.entry_repository.get_active_session(user_id)

    # Statistics Methods

    async def get_statistics(
        self, 
        user_id: int, 
        period: Optional[str] = None
    ) -> TimeTrackingStats:
        """Get time tracking statistics"""
        reference_date = date.today()
        stats = self.entry_repository.get_statistics(user_id, reference_date)
        
        return TimeTrackingStats(**stats)

    # Settings Methods

    async def get_settings(self, user_id: int) -> TimeTrackingSettings:
        """Get time tracking settings for a user"""
        settings = self.settings_repository.get_by_user_id(user_id)
        
        # Create default settings if none exist
        if not settings:
            logger.info(f"Creating default time tracking settings for user {user_id}")
            settings_data = TimeTrackingSettingsCreate()
            settings = self.settings_repository.create_settings(user_id, settings_data)
        
        return settings

    async def update_settings(
        self, 
        user_id: int, 
        data: TimeTrackingSettingsUpdate
    ) -> TimeTrackingSettings:
        """Update time tracking settings"""
        settings = self.settings_repository.get_by_user_id(user_id)
        
        if not settings:
            # Create settings if they don't exist
            settings_data = TimeTrackingSettingsCreate(
                default_hourly_rate=data.default_hourly_rate or 50.0,
                currency=data.currency or "USD"
            )
            settings = self.settings_repository.create_settings(user_id, settings_data)
        else:
            settings = self.settings_repository.update_settings(settings, data)
        
        logger.info(f"Updated time tracking settings for user {user_id}")
        return settings 