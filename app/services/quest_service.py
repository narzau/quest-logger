# app/services/quest_service.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import File, HTTPException, Depends

from app import schemas
from app.core.config import settings
from app.models.quest import Quest, QuestRarity, QuestType
from app.repositories.quest_repository import QuestRepository
from app.services.user_service import UserService
from app.services.progression_service import ProgressionService
from app.services.google_calendar_service import GoogleCalendarService
from app.integrations.chat_completion import ChatCompletionService
from app.integrations.speech import get_stt_service

import logging

logger = logging.getLogger(__name__)

class QuestService:
    """Service for quest operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = QuestRepository(db)
        self.user_service = UserService(db)
        self.progression_service = ProgressionService(db)
        self.calendar_service = GoogleCalendarService(db)
        self.chat_completion_service: ChatCompletionService = ChatCompletionService()
        self.stt_service = get_stt_service()
        
        
    def get_quests(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        quest_type: Optional[str] = None,
        is_completed: Optional[bool] = None,
    ) -> List[Quest]:
        """Get quests for a user with optional filtering."""
        # Convert string type to enum if provided
        quest_type_enum = None
        if quest_type:
            try:
                quest_type_enum = QuestType(quest_type)
            except ValueError:
                logger.warning(f"Invalid quest type: {quest_type}")
        
        return self.repository.get_user_quests(
            user_id=user_id,
            skip=skip,
            limit=limit,
            quest_type=quest_type_enum,
            is_completed=is_completed
        )
    
    def get_quest(self, user_id: int, quest_id: int) -> Optional[Quest]:
        """Get a specific quest."""
        return self.repository.get_user_quest_by_id(user_id, quest_id)
    
    def create_quest(
        self, 
        user_id: int, 
        quest_data: schemas.QuestCreate,
    ) -> Quest:
        """Create a new quest."""
        # Calculate exp reward
        user = self.user_service.get_user(user_id)
        exp_reward = self._calculate_quest_exp_reward(
            rarity=quest_data.rarity,
            quest_type=quest_data.quest_type,
            priority=quest_data.priority,
            user_level=user.level
        )
        quest_data.exp_reward = exp_reward
        
        # Create quest
        quest = self.repository.create_quest(user_id, quest_data)
        
        # Create Google Calendar event if requested
        if quest_data.google_calendar:
            try:
                event_id = self.calendar_service.create_calendar_event(user_id, quest)
                if event_id:
                    quest.google_calendar_event_id = event_id
                    self.repository.save(quest)
                    logger.info(f"Created Google Calendar event {event_id} for quest {quest.id}")
            except Exception as e:
                logger.error(f"Error creating Google Calendar event for quest {quest.id}: {e}")
        
        return quest
    
    def update_quest(
        self,
        user_id: int,
        quest_id: int,
        update_data: schemas.QuestUpdate
    ) -> Optional[Quest]:
        """Update an existing quest."""
        quest = self.repository.get_user_quest_by_id(user_id, quest_id)
        if not quest:
            return None
        
        # Store completion status before update
        was_completed_before = quest.is_completed
        
        # Update quest
        quest = self.repository.update_quest(quest, update_data)
        
        # Check if quest was just completed
        if not was_completed_before and quest.is_completed:
            # Trigger completion logic
          if not quest.completed_at:
            quest.completed_at = datetime.now()
            self.repository.save(quest)
        
          self.progression_service.handle_quest_completion(user_id, quest)
        
        # Update Google Calendar event if exists
        if quest.google_calendar_event_id:
            try:
                self.calendar_service.update_calendar_event(user_id, quest)
            except Exception as e:
                logger.error(f"Error updating Google Calendar event for quest {quest.id}: {e}")
        return quest
    
    def delete_quest(self, user_id: int, quest_id: int) -> bool:
        """Delete a quest."""
        quest = self.repository.get_user_quest_by_id(user_id, quest_id)
        if not quest:
            return False
        
        # Delete Google Calendar event if exists
        if quest.google_calendar_event_id:
            try:
                self.calendar_service.delete_calendar_event(user_id, quest)
            except Exception as e:
                logger.error(f"Error deleting Google Calendar event for quest {quest.id}: {e}")
        
        # Delete quest
        return self.repository.delete_quest(quest)
    
    async def create_quest_from_audio(
        self, 
        user_id: int,
        audio_file: File,
        language: str,
        google_calendar: bool = False
    ) -> Quest:
        """Create a new quest."""
        transcription_result = await self.stt_service.transcribe(
            audio_file=audio_file,
            language=language,
        )


        try:
            quest_in = await self.chat_completion_service.parse_quest_from_text(
                transcription_result.text, language, "Argentina"
            )
        except ValueError as e:
            logger.error(f"Error parsing quest from text: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="We couldn't turn your voice into a quest",
            )

       

        exp_reward = self._calculate_quest_exp_reward(
            rarity=quest_in.rarity,
            quest_type=quest_in.quest_type,
            priority=quest_in.priority,
        )
        quest_in.exp_reward = exp_reward
        quest = self.repository.create_quest(user_id, quest_in)
        
        if google_calendar:
            try:
                event_id = self.calendar_service.create_calendar_event(user_id, quest)
                if event_id:
                    quest.google_calendar_event_id = event_id
                    self.repository.save(quest)
                    logger.info(f"Created Google Calendar event {event_id} for quest {quest.id}")
            except Exception as e:
                logger.error(f"Error creating Google Calendar event for quest {quest.id}: {e}")
        
        logger.info(f"Quest created successfully with ID {quest.id}")
        return quest

    def _calculate_quest_exp_reward(
        self, rarity: QuestRarity, quest_type: QuestType, priority: int, user_level: int = 1
    ) -> int:
        """
        Calculate experience reward for a quest with very conservative values.
        """
        # Ensure priority is in the expected 1-100 range
        capped_priority = min(max(priority, 1), 100)
        
        # Base XP by rarity - minimal multipliers
        rarity_multipliers = {
            QuestRarity.COMMON: 1.0,
            QuestRarity.UNCOMMON: 1.2,
            QuestRarity.RARE: 1.4,
            QuestRarity.EPIC: 2,
            QuestRarity.LEGENDARY: 3.0,
        }

        # Base XP by quest type
        type_base_xp = {
            QuestType.DAILY: settings.BASE_XP_DAILY_QUEST,      # Default: 5
            QuestType.REGULAR: settings.BASE_XP_REGULAR_QUEST,  # Default: 10
            QuestType.EPIC: settings.BASE_XP_EPIC_QUEST,        # Default: 25
            QuestType.BOSS: settings.BASE_XP_BOSS_QUEST,        # Default: 50
        }

        # Priority multiplier - very modest
        priority_multiplier = 0.9 + (capped_priority * 0.1)  # 1.0 - 1.4
        
        # Almost no level scaling
        level_factor = 1.0 + (min(user_level, 30) - 1) * 0.7  # Max 1.58 at level 30
        
        # Calculate base XP
        base_xp = type_base_xp[quest_type]
        calculated_xp = int(base_xp * rarity_multipliers[rarity] * priority_multiplier * level_factor)
        
        # Hard cap based on level - MUCH more conservative
        # Only 5% of level XP for most quests, max 10% for truly exceptional quests
        xp_for_next_level = self._calculate_xp_for_next_level(user_level)
        standard_cap = int(xp_for_next_level * 0.05)  # 5% of level XP
        
        # Exceptional quest cap (legendary + boss + max priority)
        exceptional_cap = int(xp_for_next_level * 0.1)  # 10% of level XP
        is_exceptional = (
            rarity == QuestRarity.LEGENDARY and
            quest_type == QuestType.BOSS and
            capped_priority >= 4
        )
        
        # Apply appropriate cap
        max_reward = exceptional_cap if is_exceptional else standard_cap
        
        # Ensure minimum meaningful reward (doesn't go below base values)
        min_reward = max(base_xp, 5)
        
        # Final capped value
        return max(min(calculated_xp, max_reward), min_reward)
    def _calculate_xp_for_next_level(self, level: int) -> int:
        """Calculate XP needed for next level."""
        return int(100 * (level**1.5))