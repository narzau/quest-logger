# app/schemas/achievement.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# Shared properties
class AchievementBase(BaseModel):
    name: str
    description: str
    icon: Optional[str] = None
    exp_reward: int = 50


# Properties to receive on achievement creation
class AchievementCreate(AchievementBase):
    pass


# Properties to receive on achievement update
class AchievementUpdate(AchievementBase):
    name: Optional[str] = None
    description: Optional[str] = None


class AchievementInDBBase(AchievementBase):
    id: int

    class Config:
        from_attributes = True


# Additional properties to return via API
class Achievement(AchievementInDBBase):
    pass


# User Achievement Schema
class UserAchievementBase(BaseModel):
    achievement_id: int


class UserAchievementCreate(UserAchievementBase):
    pass


class UserAchievement(UserAchievementBase):
    id: int
    user_id: int
    unlocked_at: datetime
    achievement: Achievement

    class Config:
        from_attributes = True
