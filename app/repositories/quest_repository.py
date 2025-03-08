# app/repositories/quest_repository.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.repositories.base_repository import BaseRepository
from app.models.quest import Quest, QuestRarity, QuestType
from app import schemas


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest operations."""

    def __init__(self, db: Session):
        super().__init__(Quest, db)

    def get_user_quests(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        quest_type: Optional[QuestType] = None,
        is_completed: Optional[bool] = None,
    ) -> List[Quest]:
        """Get quests for a specific user with optional filtering."""
        query = self.db.query(Quest).filter(Quest.owner_id == user_id)

        if quest_type:
            query = query.filter(Quest.quest_type == quest_type)

        if is_completed is not None:
            query = query.filter(Quest.is_completed == is_completed)

        return query.offset(skip).limit(limit).all()

    def get_user_quest_by_id(self, user_id: int, quest_id: int) -> Optional[Quest]:
        """Get a specific quest for a user."""
        return (
            self.db.query(Quest)
            .filter(Quest.id == quest_id, Quest.owner_id == user_id)
            .first()
        )

    def create_quest(self, user_id: int, quest_data: schemas.QuestCreate) -> Quest:
        """Create a new quest for a user."""
        quest = Quest(
            **quest_data.model_dump(exclude={"google_calendar"}),
            owner_id=user_id,
        )
        self.db.add(quest)
        self.db.commit()
        self.db.refresh(quest)
        return quest

    def update_quest(self, quest: Quest, quest_data: schemas.QuestUpdate) -> Quest:
        """Update an existing quest."""
        quest_data_dict = quest_data.dict(exclude_unset=True)
        print(quest_data_dict)
        for field, value in quest_data_dict.items():
            if hasattr(quest, field):
                setattr(quest, field, value)
        print("asdasd")
        self.db.add(quest)
        self.db.commit()
        self.db.refresh(quest)
        print(quest.__dict__)
        return quest

    def delete_quest(self, quest: Quest) -> bool:
        """Delete a quest."""
        self.db.delete(quest)
        self.db.commit()
        return True

    def save_calendar_event_id(self, quest_id: int, event_id: str) -> bool:
        """Save Google Calendar event ID for a quest."""
        quest = self.get(quest_id)
        if not quest:
            return False

        quest.google_calendar_event_id = event_id
        self.db.add(quest)
        self.db.commit()
        return True

    def clear_calendar_event_id(self, quest_id: int) -> bool:
        """Clear Google Calendar event ID for a quest."""
        quest = self.get(quest_id)
        if not quest:
            return False

        quest.google_calendar_event_id = None
        self.db.add(quest)
        self.db.commit()
        return True
