from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, Boolean, Date
from sqlalchemy.orm import relationship
from enum import StrEnum

from app.db.base import Base


class TimeEntryPaymentStatus(StrEnum):
    NOT_PAID = "not_paid"
    INVOICED_NOT_APPROVED = "invoiced_not_approved"
    INVOICED_APPROVED = "invoiced_approved"
    PAID = "paid"


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    
    # Date and time fields
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)  # Nullable for active sessions
    
    # Financial fields
    hourly_rate = Column(Float, nullable=False)
    total_hours = Column(Float, nullable=True)
    total_earned = Column(Float, nullable=True)
    
    # Status and metadata
    payment_status = Column(String, default=TimeEntryPaymentStatus.NOT_PAID)
    notes = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="time_entries")


class TimeTrackingSettings(Base):
    __tablename__ = "time_tracking_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Default settings
    default_hourly_rate = Column(Float, default=50.0)
    currency = Column(String, default="USD")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="time_tracking_settings") 