# app/repositories/achievement_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session

from app import models
from app.repositories.achievement_repository import AchievementRepository


class AchievementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AchievementRepository(db)

    def get_all(self) -> List[models.Achievement]:
        """Get all achievements with criteria."""
        return self.repository.get_all()

    def get_by_id(self, achievement_id: int) -> Optional[models.Achievement]:
        """Get achievement by ID."""
        return self.repository.get_by_id(achievement_id)

    def get_criteria_by_type(
        self, criterion_type: str
    ) -> List[models.AchievementCriterion]:
        """Get all criteria of specified type."""
        return self.repository.get_criteria_by_type(criterion_type)

    def get_user_achievements(self, user_id: int) -> List[models.UserAchievement]:
        """Get all achievements earned by user."""
        return self.repository.get_user_achievements(user_id)

    def get_user_progress(
        self, user_id: int, criterion_id: int
    ) -> Optional[models.UserAchievementProgress]:
        """Get user's progress for specific criterion."""
        return self.repository.get_user_progress(user_id, criterion_id)

    def get_user_all_progress(
        self, user_id: int
    ) -> List[models.UserAchievementProgress]:
        """Get all progress records for user."""
        return self.repository.get_user_all_progress(user_id)

    def create_or_update_progress(
        self, user_id: int, criterion_id: int, progress_value: int
    ) -> models.UserAchievementProgress:
        """Create or update progress record."""
        return self.repository.create_or_update_progress(
            user_id, criterion_id, progress_value
        )

    def create_user_achievement(
        self, user_id: int, achievement_id: int
    ) -> models.UserAchievement:
        """Create user achievement record."""
        return self.repository.create_user_achievement(user_id, achievement_id)

    def increment_user_achievement(
        self, user_achievement: models.UserAchievement
    ) -> models.UserAchievement:
        """Increment times earned for repeatable achievement."""
        return self.repository.increment_user_achievement(user_achievement)
