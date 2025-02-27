# app/services/gamification_service.py
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session

from app import models
from app.models.quest import QuestRarity, QuestType
from app.core.config import settings

def calculate_quest_exp_reward(
    rarity: QuestRarity, 
    quest_type: QuestType, 
    priority: int
) -> int:
    """
    Calculate experience reward for a quest based on rarity, type, and priority.
    """
    # Base XP by rarity
    rarity_multipliers = {
        QuestRarity.COMMON: 1,
        QuestRarity.UNCOMMON: 1.5,
        QuestRarity.RARE: 2,
        QuestRarity.EPIC: 3,
        QuestRarity.LEGENDARY: 5
    }
    
    # Base XP by quest type from settings
    type_base_xp = {
        QuestType.DAILY: settings.BASE_XP_DAILY_QUEST,
        QuestType.REGULAR: settings.BASE_XP_REGULAR_QUEST,
        QuestType.EPIC: settings.BASE_XP_EPIC_QUEST,
        QuestType.BOSS: settings.BASE_XP_BOSS_QUEST
    }
    
    # Priority multiplier (1-5)
    priority_multiplier = 0.8 + (priority * 0.2)  # 1.0 - 1.8
    
    base_xp = type_base_xp[quest_type]
    total_xp = int(base_xp * rarity_multipliers[rarity] * priority_multiplier)
    
    return total_xp

def calculate_xp_for_next_level(level: int) -> int:
    """
    Calculate XP required for the next level.
    Uses a common RPG formula: 100 * (level^1.5)
    """
    return int(100 * (level ** 1.5))


def check_and_apply_level_up(db: Session, user: models.User) -> bool:
    """
    Check if user has enough XP to level up and apply the level up if so.
    Returns True if user leveled up, False otherwise.
    """
    xp_needed = calculate_xp_for_next_level(user.level)
    
    if user.experience >= xp_needed:
        user.level += 1
        # We don't reset experience, just let it accumulate
        db.add(user)
        db.commit()
        db.refresh(user)
        return True
    
    return False


def check_and_award_achievements(db: Session, user: models.User) -> List[models.Achievement]:
    """
    Check if user has unlocked any new achievements and award them.
    Returns a list of newly unlocked achievements.
    """
    # Get all possible achievements
    all_achievements = db.query(models.Achievement).all()
    
    # Get user's already unlocked achievements
    unlocked_achievement_ids = [
        ua.achievement_id for ua in 
        db.query(models.UserAchievement)
        .filter(models.UserAchievement.user_id == user.id)
        .all()
    ]
    
    # Get user's stats for achievement checks
    completed_quests_count = (
        db.query(models.Quest)
        .filter(models.Quest.owner_id == user.id, models.Quest.is_completed == True)
        .count()
    )
    
    # Example achievement criteria
    achievement_criteria = {
        "task_master_1": lambda: completed_quests_count >= 10,
        "task_master_2": lambda: completed_quests_count >= 50,
        "task_master_3": lambda: completed_quests_count >= 100,
        "level_up_1": lambda: user.level >= 5,
        "level_up_2": lambda: user.level >= 10,
        "level_up_3": lambda: user.level >= 20,
        # Add more achievement criteria as needed
    }
    
    newly_unlocked = []
    
    # Check each achievement
    for achievement in all_achievements:
        # Skip if already unlocked
        if achievement.id in unlocked_achievement_ids:
            continue
        
        # Check if achievement criteria is met
        # This is a simple example - you would need to map achievement names to criteria
        achievement_key = achievement.name.lower().replace(" ", "_")
        if achievement_key in achievement_criteria and achievement_criteria[achievement_key]():
            # Award achievement
            user_achievement = models.UserAchievement(
                user_id=user.id,
                achievement_id=achievement.id
            )
            db.add(user_achievement)
            
            # Award XP for achievement
            user.experience += achievement.exp_reward
            db.add(user)
            
            newly_unlocked.append(achievement)
    
    if newly_unlocked:
        db.commit()
    
    return newly_unlocked