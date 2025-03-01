import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from app import models
from app.models.quest import QuestRarity, QuestType
from app.core.config import settings


def calculate_quest_exp_reward(
    rarity: QuestRarity, quest_type: QuestType, priority: int
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
        QuestRarity.LEGENDARY: 5,
    }

    # Base XP by quest type from settings
    type_base_xp = {
        QuestType.DAILY: settings.BASE_XP_DAILY_QUEST,
        QuestType.REGULAR: settings.BASE_XP_REGULAR_QUEST,
        QuestType.EPIC: settings.BASE_XP_EPIC_QUEST,
        QuestType.BOSS: settings.BASE_XP_BOSS_QUEST,
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
    return int(100 * (level**1.5))


def check_and_apply_level_up(db: Session, user: models.User) -> bool:
    """
    Check if user has enough XP to level up and apply the level up if so.
    Returns True if user leveled up, False otherwise.
    """
    original_level = user.level
    xp_needed = calculate_xp_for_next_level(user.level)

    # Track level increases
    while user.experience >= xp_needed:
        user.level += 1
        xp_needed = calculate_xp_for_next_level(user.level)

    if user.level > original_level:
        db.add(user)
        db.commit()  # Commit level change first
        update_level_progress(db, user)
        return True

    return False


def update_level_progress(db: Session, user: models.User):
    """Update progress for all level-based criteria"""
    level_criteria = (
        db.query(models.AchievementCriterion)
        .filter(models.AchievementCriterion.criterion_type == "user_level")
        .all()
    )

    for criterion in level_criteria:
        progress = (
            db.query(models.UserAchievementProgress)
            .filter(
                models.UserAchievementProgress.user_id == user.id,
                models.UserAchievementProgress.criterion_id == criterion.id,
            )
            .first()
        )

        if not progress:
            progress = models.UserAchievementProgress(
                user_id=user.id, criterion_id=criterion.id, progress=user.level
            )
            db.add(progress)
        else:
            progress.progress = max(progress.progress, user.level)
            db.add(progress)

    db.commit()
    check_achievements(db, user)


def check_achievements(db: Session, user: models.User):
    new_achievements = []

    all_achievements = (
        db.query(models.Achievement)
        .options(joinedload(models.Achievement.criteria))
        .all()
    )

    for achievement in all_achievements:
        # Skip if non-repeatable and already earned
        if not achievement.is_repeatable and any(
            ua.achievement_id == achievement.id for ua in user.achievements
        ):
            continue

        all_met = True
        for criterion in achievement.criteria:
            progress = next(
                (
                    p
                    for p in user.achievement_progress
                    if p.criterion_id == criterion.id
                ),
                None,
            )

            # Handle level comparison differently
            if criterion.criterion_type == "user_level":
                current_value = user.level
            else:
                current_value = progress.progress if progress else 0

            if current_value < criterion.target_value:
                all_met = False
                break

        if all_met:
            existing = next(
                (ua for ua in user.achievements if ua.achievement_id == achievement.id),
                None,
            )

            if existing and achievement.is_repeatable:
                existing.times_earned += 1
                existing.unlocked_at = datetime.utcnow()
                db.add(existing)
            elif not existing:
                user_achievement = models.UserAchievement(
                    user_id=user.id, achievement_id=achievement.id
                )
                db.add(user_achievement)

            user.experience += achievement.exp_reward
            new_achievements.append(achievement)

    if new_achievements:
        db.commit()

    return new_achievements


def update_progress_and_check_achievements(
    db: Session, user: models.User, criterion_type: str, amount: int = 1
):
    # Update progress for matching criteria
    criteria = (
        db.query(models.AchievementCriterion)
        .filter(models.AchievementCriterion.criterion_type == criterion_type)
        .all()
    )

    for criterion in criteria:
        progress = (
            db.query(models.UserAchievementProgress)
            .filter(
                models.UserAchievementProgress.user_id == user.id,
                models.UserAchievementProgress.criterion_id == criterion.id,
            )
            .first()
        )

        if not progress:
            progress = models.UserAchievementProgress(
                user_id=user.id,
                criterion_id=criterion.id,
                progress=min(amount, criterion.target_value),
            )
            db.add(progress)
        else:
            new_progress = min(progress.progress + amount, criterion.target_value)
            if new_progress != progress.progress:
                progress.progress = new_progress
                db.add(progress)

    db.commit()
    check_achievements(db, user)
