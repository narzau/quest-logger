from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)

    # Gamification stats
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)

    # Relationships
    quests = relationship("Quest", back_populates="owner")
    achievements = relationship("UserAchievement", back_populates="user")
    achievement_progress = relationship("UserAchievementProgress")
