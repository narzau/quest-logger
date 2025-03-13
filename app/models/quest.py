import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class QuestRarity(str, enum.Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class QuestType(str, enum.Enum):
    DAILY = "daily"
    REGULAR = "regular"
    EPIC = "epic"
    BOSS = "boss"


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    rarity = Column(Enum(QuestRarity), default=QuestRarity.COMMON)
    quest_type = Column(Enum(QuestType), default=QuestType.REGULAR)
    priority = Column(Integer, default=1)  # 1 (low) to 5 (high)
    exp_reward = Column(Integer, default=10)
    owner_id = Column(Integer, ForeignKey("users.id"))
    parent_quest_id = Column(Integer, ForeignKey("quests.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    tracked = Column(Boolean, default=True)
    google_calendar_event_id = Column(String, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="quests")
    sub_quests = relationship("Quest", backref="parent_quest", remote_side=[id])
    notes = relationship("Note", back_populates="quest")
