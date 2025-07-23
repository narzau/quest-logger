from datetime import datetime, date
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from app.models.time_tracking import TimeEntryPaymentStatus


# Base schemas
class TimeEntryBase(BaseModel):
    date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    hourly_rate: float
    payment_status: TimeEntryPaymentStatus = TimeEntryPaymentStatus.NOT_PAID
    notes: Optional[str] = None


# Create schemas
class TimeEntryCreate(TimeEntryBase):
    pass


class SessionStart(BaseModel):
    hourly_rate: float


# Update schemas
class TimeEntryUpdate(BaseModel):
    date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    hourly_rate: Optional[float] = None
    payment_status: Optional[TimeEntryPaymentStatus] = None
    notes: Optional[str] = None


# Response schemas
class TimeEntry(TimeEntryBase):
    id: int
    user_id: int
    total_hours: Optional[float] = None
    total_earned: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Settings schemas
class TimeTrackingSettingsBase(BaseModel):
    default_hourly_rate: float = 50.0
    currency: str = "USD"


class TimeTrackingSettingsCreate(TimeTrackingSettingsBase):
    pass


class TimeTrackingSettingsUpdate(BaseModel):
    default_hourly_rate: Optional[float] = None
    currency: Optional[str] = None


class TimeTrackingSettings(TimeTrackingSettingsBase):
    class Config:
        from_attributes = True


# Statistics schema
class TimeTrackingStats(BaseModel):
    total_hours_today: float
    total_earned_today: float
    total_hours_week: float
    total_earned_week: float
    total_hours_month: float
    total_earned_month: float
    unpaid_amount: float
    invoiced_amount: float
    paid_amount: float


# List response with pagination
class TimeEntryList(BaseModel):
    items: list[TimeEntry]
    total: int
    page: int
    size: int
    pages: int


# Invoice link generation
class GenerateInvoiceLinkRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    payment_status: Optional[TimeEntryPaymentStatus] = None
    expires_in_days: int = Field(default=30, ge=1, le=365)


class GenerateInvoiceLinkResponse(BaseModel):
    public_url: str 