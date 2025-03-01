from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    icon = Column(String, nullable=True)
    exp_reward = Column(Integer, default=50)
    is_repeatable = Column(Boolean, default=False)
    criteria = relationship("AchievementCriterion", back_populates="achievement")


class AchievementCriterion(Base):
    __tablename__ = "achievement_criteria"

    id = Column(Integer, primary_key=True, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    criterion_type = Column(String, nullable=False)  # e.g., 'quests_completed', 'level'
    target_value = Column(Integer, nullable=False)

    achievement = relationship("Achievement", back_populates="criteria")


class UserAchievementProgress(Base):
    __tablename__ = "user_achievement_progress"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    criterion_id = Column(
        Integer, ForeignKey("achievement_criteria.id"), primary_key=True
    )
    progress = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    criterion = relationship("AchievementCriterion")


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    times_earned = Column(Integer, default=1)  # For repeatable achievements

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement")
