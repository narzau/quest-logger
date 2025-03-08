# app/repositories/achievement_repository.py
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from app import models

class AchievementService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_all(self) -> List[models.Achievement]:
        """Get all achievements with criteria."""
        return self.db.query(models.Achievement)\
            .options(joinedload(models.Achievement.criteria))\
            .all()
    
    def get_by_id(self, achievement_id: int) -> Optional[models.Achievement]:
        """Get achievement by ID."""
        return self.db.query(models.Achievement).filter(
            models.Achievement.id == achievement_id
        ).first()
    
    def get_criteria_by_type(self, criterion_type: str) -> List[models.AchievementCriterion]:
        """Get all criteria of specified type."""
        return self.db.query(models.AchievementCriterion).filter(
            models.AchievementCriterion.criterion_type == criterion_type
        ).all()
    
    def get_user_achievements(self, user_id: int) -> List[models.UserAchievement]:
        """Get all achievements earned by user."""
        return self.db.query(models.UserAchievement).filter(
            models.UserAchievement.user_id == user_id
        ).all()
    
    def get_user_progress(self, user_id: int, criterion_id: int) -> Optional[models.UserAchievementProgress]:
        """Get user's progress for specific criterion."""
        return self.db.query(models.UserAchievementProgress).filter(
            models.UserAchievementProgress.user_id == user_id,
            models.UserAchievementProgress.criterion_id == criterion_id
        ).first()
    
    def get_user_all_progress(self, user_id: int) -> List[models.UserAchievementProgress]:
        """Get all progress records for user."""
        return self.db.query(models.UserAchievementProgress).filter(
            models.UserAchievementProgress.user_id == user_id
        ).all()
    
    def create_or_update_progress(self, user_id: int, criterion_id: int, progress_value: int) -> models.UserAchievementProgress:
        """Create or update progress record."""
        progress = self.get_user_progress(user_id, criterion_id)
        
        if not progress:
            progress = models.UserAchievementProgress(
                user_id=user_id,
                criterion_id=criterion_id,
                progress=progress_value,
                last_updated=datetime.utcnow()
            )
        else:
            progress.progress = progress_value
            progress.last_updated = datetime.utcnow()
            
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress
    
    def create_user_achievement(self, user_id: int, achievement_id: int) -> models.UserAchievement:
        """Create user achievement record."""
        achievement = models.UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            unlocked_at=datetime.utcnow(),
            times_earned=1
        )
        self.db.add(achievement)
        self.db.commit()
        self.db.refresh(achievement)
        return achievement
    
    def increment_user_achievement(self, user_achievement: models.UserAchievement) -> models.UserAchievement:
        """Increment times earned for repeatable achievement."""
        user_achievement.times_earned += 1
        user_achievement.unlocked_at = datetime.utcnow()
        self.db.add(user_achievement)
        self.db.commit()
        self.db.refresh(user_achievement)
        return user_achievement