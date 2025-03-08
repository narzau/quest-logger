# app/schemas/__init__.py
from app.schemas.token import Token, TokenPayload
from app.schemas.user import User, UserCreate, UserInDB, UserUpdate, UserLogin, UserUpdateProgression
from app.schemas.quest import Quest, QuestCreate, QuestUpdate
from app.schemas.achievement import (
    Achievement,
    AchievementCreate,
    UserAchievement,
    UserAchievementCreate,
)
