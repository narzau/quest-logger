from app.db.base import Base

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone


class GoogleCalendarIntegration(Base):
    """
    Google Calendar specific integration model.
    """
    __tablename__ = "google_calendar_integration"

    id = Column(Integer, primary_key=True, index=True)
    oauth_state = Column(String, nullable=True)  # For OAuth flow
    selected_calendar_id = Column(String, nullable=True)
    selected_calendar_name = Column(String, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scopes = Column(String, nullable=True)
    connection_status = Column(String, nullable=True)
    
    config = Column(JSON, nullable=True)
    
    user = relationship("User", back_populates="google_calendar_integration")
