# app/services/progression_service.py
import logging
from typing import List, Tuple, Set
from datetime import datetime

from sqlalchemy.orm import Session
from app import models
from app.models.quest import QuestRarity, QuestType
from app.repositories.user_repository import UserRepository
from app.repositories.achievement_repository import AchievementRepository

logger = logging.getLogger(__name__)

class ProgressionService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.achievement_repository = AchievementRepository(db)
    
    def handle_quest_completion(self, user_id: int, quest: models.Quest) -> Tuple[bool, List[models.Achievement]]:
        """Handle quest completion progression."""
        # Track state for debugging
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return False, []
            
        initial_xp = user.experience
        initial_level = user.level
        
        # Add ONLY the quest XP
        user.experience += quest.exp_reward
        self.user_repository.update(user)
        logger.info(f"Quest XP added: {quest.exp_reward}")
        
        # Update all relevant achievement progress
        self._update_quest_achievement_progress(user_id, quest)
        
        # Track processed achievements to prevent duplicates
        processed_achievement_ids = set()
        
        # Process all achievements with careful tracking
        leveled_up, newly_unlocked = self._process_achievements_and_levels(
            user_id, processed_achievement_ids
        )
        
        # Final log for verification
        user = self.user_repository.get_by_id(user_id)
        logger.info(f"Total XP change: {user.experience - initial_xp} (Quest: {quest.exp_reward})")
        logger.info(f"Level change: {initial_level} -> {user.level}")
        
        return leveled_up, newly_unlocked
    
    def _update_quest_achievement_progress(self, user_id: int, quest: models.Quest) -> None:
        """Update achievement progress based on quest properties."""
        # Basic quest completion
        self._update_progress(user_id, "quests_completed", 1)
        
        # Type-specific
        if quest.quest_type == QuestType.BOSS:
            self._update_progress(user_id, "boss_quests_completed", 1)
        elif quest.quest_type == QuestType.EPIC:
            self._update_progress(user_id, "epic_quests_completed", 1)
        
        # Rarity-specific
        if quest.rarity == QuestRarity.LEGENDARY:
            self._update_progress(user_id, "legendary_quests_completed", 1)
        
        # Time-based
        completion_time = quest.completed_at or datetime.utcnow()
        completion_hour = completion_time.hour
        
        if completion_hour < 8:
            self._update_progress(user_id, "early_morning_completion", 1)
        elif completion_hour >= 22:
            self._update_progress(user_id, "late_night_completion", 1)
    
    def _update_progress(self, user_id: int, criterion_type: str, amount: int) -> None:
        """Update achievement progress."""
        criteria = self.achievement_repository.get_criteria_by_type(criterion_type)
        
        for criterion in criteria:
            progress = self.achievement_repository.get_user_progress(user_id, criterion.id)
            
            # Calculate new value
            if criterion_type == "user_level":
                user = self.user_repository.get_by_id(user_id)
                new_value = user.level
            else:
                current_value = progress.progress if progress else 0
                new_value = min(current_value + amount, criterion.target_value)
            
            # Only update if changed
            if not progress or progress.progress != new_value:
                self.achievement_repository.create_or_update_progress(
                    user_id, criterion.id, new_value
                )
    
    def _process_achievements_and_levels(
        self, user_id: int, processed_achievement_ids: Set[int]
    ) -> Tuple[bool, List[models.Achievement]]:
        """
        Process achievements and level-ups carefully to prevent duplicates.
        Returns (did_level_up, newly_unlocked_achievements)
        """
        user = self.user_repository.get_by_id(user_id)
        original_level = user.level
        newly_unlocked = []
        
        # First check for potential new achievements
        unlocked = self._check_achievements(user_id, processed_achievement_ids)
        if unlocked:
            newly_unlocked.extend(unlocked)
            
            # Award XP for new achievements
            total_achievement_xp = sum(a.exp_reward for a in unlocked)
            if total_achievement_xp > 0:
                user = self.user_repository.get_by_id(user_id)  # Refresh user
                user.experience += total_achievement_xp
                self.user_repository.update(user)
                logger.info(f"Achievement XP added: {total_achievement_xp}")
        
        # Check for level-ups (just once)
        leveled_up = self._check_for_level_up(user_id)
        
        # If user leveled up, check for level-based achievements
        if leveled_up:
            # Update level-based progress
            user = self.user_repository.get_by_id(user_id)  # Refresh user
            self._update_progress(user_id, "user_level", user.level)
            
            # Check for level-based achievements
            level_achievements = self._check_achievements(user_id, processed_achievement_ids)
            if level_achievements:
                newly_unlocked.extend(level_achievements)
                
                # Award XP for level-based achievements
                level_achievement_xp = sum(a.exp_reward for a in level_achievements)
                if level_achievement_xp > 0:
                    user = self.user_repository.get_by_id(user_id)  # Refresh user
                    user.experience += level_achievement_xp
                    self.user_repository.update(user)
                    logger.info(f"Level achievement XP added: {level_achievement_xp}")
        
        return leveled_up, newly_unlocked
    
    def _check_for_level_up(self, user_id: int) -> bool:
        """Check if user should level up and apply it if needed."""
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return False
            
        original_level = user.level
        
        # Keep leveling up while user has enough XP
        while True:
            xp_needed = self._calculate_xp_for_next_level(user.level)
            if user.experience >= xp_needed:
                user.level += 1
            else:
                break
        
        # If level changed, save it
        if user.level > original_level:
            self.user_repository.update(user)
            logger.info(f"User leveled up from {original_level} to {user.level}")
            return True
            
        return False
    
    def _calculate_xp_for_next_level(self, level: int) -> int:
        """Calculate XP needed for next level."""
        return int(100 * (level**1.5))
    
    def _check_achievements(
        self, user_id: int, processed_achievement_ids: Set[int]
    ) -> List[models.Achievement]:
        """
        Check for unprocessed achievements that should be unlocked.
        The processed_achievement_ids set prevents double-processing.
        """
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return []
            
        all_achievements = self.achievement_repository.get_all()
        user_achievements = self.achievement_repository.get_user_achievements(user_id)
        progress_records = self.achievement_repository.get_user_all_progress(user_id)
        
        # Map achievement IDs and progress for quick lookup
        earned_map = {ua.achievement_id: ua for ua in user_achievements}
        progress_map = {p.criterion_id: p.progress for p in progress_records}
        
        newly_unlocked = []
        
        for achievement in all_achievements:
            # Skip if already processed in this operation
            if achievement.id in processed_achievement_ids:
                continue
                
            # Skip if already earned and not repeatable
            if achievement.id in earned_map and not achievement.is_repeatable:
                continue
                
            # Mark as processed (even if not unlocked)
            processed_achievement_ids.add(achievement.id)
            
            # Check all criteria
            criteria_met = True
            for criterion in achievement.criteria:
                if criterion.criterion_type == "user_level":
                    if user.level < criterion.target_value:
                        criteria_met = False
                        break
                else:
                    current_progress = progress_map.get(criterion.id, 0)
                    if current_progress < criterion.target_value:
                        criteria_met = False
                        break
            
            if criteria_met:
                # Achievement unlocked!
                existing = earned_map.get(achievement.id)
                
                if existing and achievement.is_repeatable:
                    # Increment repeatable achievement
                    self.achievement_repository.increment_user_achievement(existing)
                    logger.info(f"Incremented repeatable achievement: {achievement.name}")
                elif not existing:
                    # Create new achievement
                    self.achievement_repository.create_user_achievement(user_id, achievement.id)
                    logger.info(f"Unlocked new achievement: {achievement.name}")
                else:
                    # Already earned non-repeatable
                    continue
                
                newly_unlocked.append(achievement)
        
        return newly_unlocked