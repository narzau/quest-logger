# app/schemas/quest.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.quest import QuestRarity, QuestType


# Shared properties
class QuestBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    rarity: QuestRarity = QuestRarity.COMMON
    quest_type: QuestType = QuestType.REGULAR
    priority: int = 1
    exp_reward: int = 10
    parent_quest_id: Optional[int] = None


# Properties to receive on quest creation
class QuestCreate(QuestBase):
    pass


# Properties to receive on quest update
class QuestUpdate(QuestBase):
    title: Optional[str] = None
    is_completed: Optional[bool] = None


class QuestInDBBase(QuestBase):
    id: int
    title: str
    is_completed: bool
    created_at: datetime
    owner_id: int

    class Config:
        from_attributes = True


# Additional properties to return via API
class Quest(QuestInDBBase):
    pass


# Additional properties stored in DB
class QuestInDB(QuestInDBBase):
    pass