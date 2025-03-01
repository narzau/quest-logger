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
    xp_needed = calculate_xp_for_next_level(user.level)

    if user.experience >= xp_needed:
        user.level += 1
        # We don't reset experience, just let it accumulate
        db.add(user)
        db.commit()
        db.refresh(user)
        return True

    return False


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
                and_(
                    models.UserAchievementProgress.user_id == user.id,
                    models.UserAchievementProgress.criterion_id == criterion.id,
                )
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
    return check_achievements(db, user)


def check_achievements(db: Session, user: models.User):
    new_achievements = []

    # Get all possible achievements
    all_achievements = (
        db.query(models.Achievement)
        .options(joinedload(models.Achievement.criteria))
        .all()
    )

    for achievement in all_achievements:
        # Check if already earned (for non-repeatable)
        if not achievement.is_repeatable:
            existing = (
                db.query(models.UserAchievement)
                .filter(
                    and_(
                        models.UserAchievement.user_id == user.id,
                        models.UserAchievement.achievement_id == achievement.id,
                    )
                )
                .first()
            )
            if existing:
                continue

        # Check all criteria
        all_met = True
        for criterion in achievement.criteria:
            progress = (
                db.query(models.UserAchievementProgress)
                .filter(
                    and_(
                        models.UserAchievementProgress.user_id == user.id,
                        models.UserAchievementProgress.criterion_id == criterion.id,
                    )
                )
                .first()
            )

            if not progress or progress.progress < criterion.target_value:
                all_met = False
                break

        if all_met:
            # Award achievement
            user_achievement = (
                db.query(models.UserAchievement)
                .filter(
                    and_(
                        models.UserAchievement.user_id == user.id,
                        models.UserAchievement.achievement_id == achievement.id,
                    )
                )
                .first()
            )

            if user_achievement and achievement.is_repeatable:
                user_achievement.times_earned += 1
                user_achievement.unlocked_at = datetime.datetime.now(
                    datetime.timezone.utc
                )()
            else:
                user_achievement = models.UserAchievement(
                    user_id=user.id, achievement_id=achievement.id
                )
                db.add(user_achievement)

            # Award XP
            user.experience += achievement.exp_reward
            new_achievements.append(achievement)

    if new_achievements:
        db.commit()

    return new_achievements
