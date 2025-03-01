# scripts/seed_data.py
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app import models


# scripts/seed_data.py (updated)
def seed_achievements(db: Session):
    """Seed initial achievements with their criteria."""
    achievements = [
        {
            "name": "Task Master I",
            "description": "Complete 10 quests",
            "icon": "🏆",
            "exp_reward": 50,
            "is_repeatable": False,
            "criteria": [
                {"type": "quests_completed", "target": 10}
            ]
        },
        {
            "name": "Task Master II",
            "description": "Complete 50 quests",
            "icon": "🏆🏆",
            "exp_reward": 150,
            "is_repeatable": False,
            "criteria": [
                {"type": "quests_completed", "target": 50}
            ]
        },
        {
            "name": "Task Master III",
            "description": "Complete 100 quests",
            "icon": "🏆🏆🏆",
            "exp_reward": 300,
            "is_repeatable": False,
            "criteria": [
                {"type": "quests_completed", "target": 100}
            ]
        },
        {
            "name": "Level Up I",
            "description": "Reach level 5",
            "icon": "⭐",
            "exp_reward": 100,
            "is_repeatable": False,
            "criteria": [
                {"type": "user_level", "target": 5}
            ]
        },
        {
            "name": "Level Up II",
            "description": "Reach level 10",
            "icon": "⭐⭐",
            "exp_reward": 200,
            "is_repeatable": False,
            "criteria": [
                {"type": "user_level", "target": 10}
            ]
        },
        {
            "name": "Level Up III",
            "description": "Reach level 20",
            "icon": "⭐⭐⭐",
            "exp_reward": 400,
            "is_repeatable": False,
            "criteria": [
                {"type": "user_level", "target": 20}
            ]
        },
        {
            "name": "Early Bird",
            "description": "Complete a task before 8 AM",
            "icon": "🐦",
            "exp_reward": 75,
            "is_repeatable": True,
            "criteria": [
                {"type": "early_morning_completion", "target": 1}
            ]
        },
        {
            "name": "Night Owl",
            "description": "Complete a task after 10 PM",
            "icon": "🦉",
            "exp_reward": 75,
            "is_repeatable": True,
            "criteria": [
                {"type": "late_night_completion", "target": 1}
            ]
        },
        {
            "name": "Legendary Quester",
            "description": "Complete a legendary quest",
            "icon": "👑",
            "exp_reward": 200,
            "is_repeatable": False,
            "criteria": [
                {"type": "legendary_quests_completed", "target": 1}
            ]
        },
        {
            "name": "Boss Slayer",
            "description": "Complete a boss quest",
            "icon": "🔥",
            "exp_reward": 300,
            "is_repeatable": False,
            "criteria": [
                {"type": "boss_quests_completed", "target": 1}
            ]
        }
    ]
    
    for achievement_data in achievements:
        criteria = achievement_data.pop("criteria", [])
        
        # Create or update achievement
        achievement = db.query(models.Achievement).filter_by(
            name=achievement_data["name"]
        ).first()
        
        if not achievement:
            achievement = models.Achievement(**achievement_data)
            db.add(achievement)
            db.commit()
            db.refresh(achievement)
        else:
            # Update existing achievement
            for key, value in achievement_data.items():
                setattr(achievement, key, value)
            db.add(achievement)
            db.commit()
        
        # Add criteria
        for criterion_data in criteria:
            criterion = db.query(models.AchievementCriterion).filter_by(
                achievement_id=achievement.id,
                criterion_type=criterion_data["type"],
                target_value=criterion_data["target"]
            ).first()
            
            if not criterion:
                db.add(models.AchievementCriterion(
                    achievement_id=achievement.id,
                    criterion_type=criterion_data["type"],
                    target_value=criterion_data["target"]
                ))
        
    db.commit()

def main():
    """Main function to seed data."""
    db = SessionLocal()
    try:
        seed_achievements(db)
        print("Database seeded successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    main()