from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.repositories.base_repository import BaseRepository
from app.models.time_tracking import TimeEntry, TimeTrackingSettings, TimeEntryPaymentStatus
from app.schemas.time_tracking import TimeEntryCreate, TimeEntryUpdate, TimeTrackingSettingsCreate, TimeTrackingSettingsUpdate


class TimeEntryRepository(BaseRepository[TimeEntry]):
    """Repository for TimeEntry operations."""

    def __init__(self, db: Session):
        super().__init__(TimeEntry, db)

    def create_time_entry(self, user_id: int, obj_in: TimeEntryCreate) -> TimeEntry:
        """Create a new time entry"""
        time_entry = TimeEntry(
            user_id=user_id,
            **obj_in.dict()
        )
        
        # Calculate totals if both start and end time are provided
        if time_entry.start_time and time_entry.end_time:
            time_entry.total_hours = self._calculate_hours(time_entry.start_time, time_entry.end_time)
            time_entry.total_earned = time_entry.total_hours * time_entry.hourly_rate
        
        self.db.add(time_entry)
        self.db.commit()
        self.db.refresh(time_entry)
        return time_entry

    def get_user_time_entry(self, user_id: int, entry_id: int) -> Optional[TimeEntry]:
        """Get a specific time entry for a user"""
        return (
            self.db.query(TimeEntry)
            .filter(TimeEntry.id == entry_id, TimeEntry.user_id == user_id)
            .first()
        )

    def get_active_session(self, user_id: int) -> Optional[TimeEntry]:
        """Get the active time entry (no end_time) for a user"""
        return (
            self.db.query(TimeEntry)
            .filter(TimeEntry.user_id == user_id, TimeEntry.end_time.is_(None))
            .first()
        )

    def stop_session(self, time_entry: TimeEntry, end_time: datetime) -> TimeEntry:
        """Stop an active session by setting end_time and calculating totals"""
        time_entry.end_time = end_time
        time_entry.total_hours = self._calculate_hours(time_entry.start_time, end_time)
        time_entry.total_earned = time_entry.total_hours * time_entry.hourly_rate
        time_entry.updated_at = datetime.utcnow()
        
        self.db.add(time_entry)
        self.db.commit()
        self.db.refresh(time_entry)
        return time_entry

    def update_time_entry(self, time_entry: TimeEntry, obj_in: TimeEntryUpdate) -> TimeEntry:
        """Update a time entry"""
        update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(time_entry, field, value)
        
        # Recalculate totals if times or rate changed
        if time_entry.start_time and time_entry.end_time:
            time_entry.total_hours = self._calculate_hours(time_entry.start_time, time_entry.end_time)
            time_entry.total_earned = time_entry.total_hours * time_entry.hourly_rate
        
        time_entry.updated_at = datetime.utcnow()
        
        self.db.add(time_entry)
        self.db.commit()
        self.db.refresh(time_entry)
        return time_entry

    def delete_time_entry(self, time_entry: TimeEntry) -> bool:
        """Delete a time entry"""
        self.db.delete(time_entry)
        self.db.commit()
        return True

    def get_user_time_entries(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        payment_status: Optional[TimeEntryPaymentStatus] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of time entries with filtering"""
        query = self.db.query(TimeEntry).filter(TimeEntry.user_id == user_id)
        
        # Apply date filters
        if start_date:
            query = query.filter(TimeEntry.date >= start_date)
        if end_date:
            query = query.filter(TimeEntry.date <= end_date)
        
        # Apply payment status filter
        if payment_status:
            query = query.filter(TimeEntry.payment_status == payment_status)
        
        # Count total before pagination
        total = query.count()
        
        # Apply sorting (newest first)
        query = query.order_by(desc(TimeEntry.date), desc(TimeEntry.start_time))
        
        # Apply pagination
        items = query.offset(skip).limit(limit).all()
        
        # Calculate total pages
        pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return {
            "items": items,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": pages,
        }

    def get_statistics(self, user_id: int, reference_date: date) -> Dict[str, float]:
        """Get time tracking statistics for a user"""
        # Calculate date ranges
        start_of_day = reference_date
        start_of_week = reference_date - timedelta(days=reference_date.weekday())
        start_of_month = reference_date.replace(day=1)
        
        # Get statistics for different periods
        stats = {
            "total_hours_today": self._get_total_hours(user_id, start_of_day, start_of_day),
            "total_earned_today": self._get_total_earned(user_id, start_of_day, start_of_day),
            "total_hours_week": self._get_total_hours(user_id, start_of_week, reference_date),
            "total_earned_week": self._get_total_earned(user_id, start_of_week, reference_date),
            "total_hours_month": self._get_total_hours(user_id, start_of_month, reference_date),
            "total_earned_month": self._get_total_earned(user_id, start_of_month, reference_date),
            "unpaid_amount": self._get_total_by_payment_status(user_id, TimeEntryPaymentStatus.NOT_PAID),
            "invoiced_amount": self._get_total_by_payment_status(
                user_id, 
                [TimeEntryPaymentStatus.INVOICED_NOT_APPROVED, TimeEntryPaymentStatus.INVOICED_APPROVED]
            ),
            "paid_amount": self._get_total_by_payment_status(user_id, TimeEntryPaymentStatus.PAID),
        }
        
        return stats

    def _calculate_hours(self, start_time: datetime, end_time: datetime) -> float:
        """Calculate hours between two times"""
        delta = end_time - start_time
        return round(delta.total_seconds() / 3600, 2)

    def _get_total_hours(self, user_id: int, start_date: date, end_date: date) -> float:
        """Get total hours for a date range"""
        result = (
            self.db.query(func.sum(TimeEntry.total_hours))
            .filter(
                TimeEntry.user_id == user_id,
                TimeEntry.date >= start_date,
                TimeEntry.date <= end_date,
                TimeEntry.total_hours.isnot(None)
            )
            .scalar()
        )
        return float(result or 0)

    def _get_total_earned(self, user_id: int, start_date: date, end_date: date) -> float:
        """Get total earned for a date range"""
        result = (
            self.db.query(func.sum(TimeEntry.total_earned))
            .filter(
                TimeEntry.user_id == user_id,
                TimeEntry.date >= start_date,
                TimeEntry.date <= end_date,
                TimeEntry.total_earned.isnot(None)
            )
            .scalar()
        )
        return float(result or 0)

    def _get_total_by_payment_status(
        self, 
        user_id: int, 
        payment_status: Optional[List[TimeEntryPaymentStatus] | TimeEntryPaymentStatus]
    ) -> float:
        """Get total earned by payment status"""
        query = self.db.query(func.sum(TimeEntry.total_earned)).filter(
            TimeEntry.user_id == user_id,
            TimeEntry.total_earned.isnot(None)
        )
        
        if isinstance(payment_status, list):
            query = query.filter(TimeEntry.payment_status.in_(payment_status))
        else:
            query = query.filter(TimeEntry.payment_status == payment_status)
        
        result = query.scalar()
        return float(result or 0)


class TimeTrackingSettingsRepository(BaseRepository[TimeTrackingSettings]):
    """Repository for TimeTrackingSettings operations."""

    def __init__(self, db: Session):
        super().__init__(TimeTrackingSettings, db)

    def get_by_user_id(self, user_id: int) -> Optional[TimeTrackingSettings]:
        """Get settings for a specific user"""
        return self.get_by(user_id=user_id)

    def create_settings(
        self, 
        user_id: int, 
        obj_in: TimeTrackingSettingsCreate
    ) -> TimeTrackingSettings:
        """Create settings for a user"""
        settings = TimeTrackingSettings(
            user_id=user_id,
            **obj_in.dict()
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_settings(
        self, 
        settings: TimeTrackingSettings, 
        obj_in: TimeTrackingSettingsUpdate
    ) -> TimeTrackingSettings:
        """Update settings"""
        update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(settings, field, value)
        
        settings.updated_at = datetime.utcnow()
        
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings 