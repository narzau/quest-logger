# app/schemas/quest.py
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel

from app.models.quest import QuestRarity, QuestType


# Shared properties
class QuestBase(BaseModel):
    title: str
    description: Optional[str] = None
    rarity: QuestRarity = QuestRarity.COMMON
    quest_type: QuestType = QuestType.REGULAR
    priority: int = 1
    exp_reward: int = 10
    parent_quest_id: Optional[int] = None
    tracked: bool = True
    due_date: Optional[datetime] = datetime.now(timezone.utc).replace(
        hour=23, minute=59, second=59
    )


# Properties to receive on quest creation
class QuestCreate(QuestBase):
  google_calendar: Optional[bool] = False


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
    google_calendar_event_id: Optional[str] = None
    class Config:
        from_attributes = True


# Additional properties to return via API
class Quest(QuestInDBBase):
    pass


# Additional properties stored in DB
class QuestInDB(QuestInDBBase):
    pass
