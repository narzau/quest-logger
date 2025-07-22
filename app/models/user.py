from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)

    # Gamification stats
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)

    # Relationships
    quests = relationship("Quest", back_populates="owner")
    notes = relationship("Note", back_populates="owner")
    achievements = relationship("UserAchievement", back_populates="user")
    achievement_progress = relationship("UserAchievementProgress")
    google_calendar_integration = relationship(
        "GoogleCalendarIntegration", back_populates="user", cascade="all, delete-orphan"
    )
    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    time_entries = relationship("TimeEntry", back_populates="user", cascade="all, delete-orphan")
    time_tracking_settings = relationship(
        "TimeTrackingSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
