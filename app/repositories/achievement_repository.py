# app/repositories/quest_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.repositories.base_repository import BaseRepository
from app import models


class AchievementRepository(BaseRepository[models.Achievement]):
    """Repository for user operations."""

    def __init__(self, db: Session):
        super().__init__(models.Achievement, db)

    def get_by_id(self, achievement_id: int) -> Optional[models.Achievement]:
        """Get achievement by ID with criteria loaded."""
        return (
            self.db.query(models.Achievement)
            .options(joinedload(models.Achievement.criteria))
            .filter(models.Achievement.id == achievement_id)
            .first()
        )

    def get_all(self) -> List[models.Achievement]:
        """Get all achievements with their criteria."""
        return (
            self.db.query(models.Achievement)
            .options(joinedload(models.Achievement.criteria))
            .all()
        )

    def get_criteria_by_type(
        self, criterion_type: str
    ) -> List[models.AchievementCriterion]:
        """Get achievement criteria by type."""
        return (
            self.db.query(models.AchievementCriterion)
            .filter(models.AchievementCriterion.criterion_type == criterion_type)
            .all()
        )

    def get_user_achievements(self, user_id: int) -> List[models.UserAchievement]:
        """Get all achievements unlocked by a user."""
        return (
            self.db.query(models.UserAchievement)
            .options(joinedload(models.UserAchievement.achievement))
            .filter(models.UserAchievement.user_id == user_id)
            .all()
        )

    def get_user_achievement(
        self, user_id: int, achievement_id: int
    ) -> Optional[models.UserAchievement]:
        """Get specific user achievement."""
        return (
            self.db.query(models.UserAchievement)
            .filter(
                models.UserAchievement.user_id == user_id,
                models.UserAchievement.achievement_id == achievement_id,
            )
            .first()
        )

    def get_user_progress(
        self, user_id: int, criterion_id: int
    ) -> Optional[models.UserAchievementProgress]:
        """Get user's progress for a specific criterion."""
        return (
            self.db.query(models.UserAchievementProgress)
            .filter(
                models.UserAchievementProgress.user_id == user_id,
                models.UserAchievementProgress.criterion_id == criterion_id,
            )
            .first()
        )

    def get_user_all_progress(
        self, user_id: int
    ) -> List[models.UserAchievementProgress]:
        """Get all progress records for a user."""
        return (
            self.db.query(models.UserAchievementProgress)
            .options(joinedload(models.UserAchievementProgress.criterion))
            .filter(models.UserAchievementProgress.user_id == user_id)
            .all()
        )

    def create_or_update_progress(
        self, user_id: int, criterion_id: int, progress_value: int
    ) -> models.UserAchievementProgress:
        """Create or update user achievement progress."""
        progress = self.get_user_progress(user_id, criterion_id)

        if not progress:
            progress = models.UserAchievementProgress(
                user_id=user_id,
                criterion_id=criterion_id,
                progress=progress_value,
                last_updated=datetime.utcnow(),
            )
        else:
            progress.progress = progress_value
            progress.last_updated = datetime.utcnow()

        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def create_user_achievement(
        self, user_id: int, achievement_id: int
    ) -> models.UserAchievement:
        """Create user achievement record."""
        user_achievement = models.UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            unlocked_at=datetime.utcnow(),
            times_earned=1,
        )
        self.db.add(user_achievement)
        self.db.commit()
        self.db.refresh(user_achievement)
        return user_achievement

    def increment_user_achievement(
        self, user_achievement: models.UserAchievement
    ) -> models.UserAchievement:
        """Increment times earned for repeatable achievements."""
        user_achievement.times_earned += 1
        user_achievement.unlocked_at = datetime.utcnow()
        self.db.add(user_achievement)
        self.db.commit()
        self.db.refresh(user_achievement)
        return user_achievement
