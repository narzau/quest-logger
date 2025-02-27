# scripts/seed_data.py
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app import models


def seed_achievements(db: Session):
    """Seed initial achievements."""
    achievements = [
        {
            "name": "Task Master I",
            "description": "Complete 10 quests",
            "icon": "🏆",
            "exp_reward": 50
        },
        {
            "name": "Task Master II",
            "description": "Complete 50 quests",
            "icon": "🏆🏆",
            "exp_reward": 150
        },
        {
            "name": "Task Master III",
            "description": "Complete 100 quests",
            "icon": "🏆🏆🏆",
            "exp_reward": 300
        },
        {
            "name": "Level Up I",
            "description": "Reach level 5",
            "icon": "⭐",
            "exp_reward": 100
        },
        {
            "name": "Level Up II",
            "description": "Reach level 10",
            "icon": "⭐⭐",
            "exp_reward": 200
        },
        {
            "name": "Level Up III",
            "description": "Reach level 20",
            "icon": "⭐⭐⭐",
            "exp_reward": 400
        },
        {
            "name": "Early Bird",
            "description": "Complete a task before 8 AM",
            "icon": "🐦",
            "exp_reward": 75
        },
        {
            "name": "Night Owl",
            "description": "Complete a task after 10 PM",
            "icon": "🦉",
            "exp_reward": 75
        },
        {
            "name": "Legendary Quester",
            "description": "Complete a legendary quest",
            "icon": "👑",
            "exp_reward": 200
        },
        {
            "name": "Boss Slayer",
            "description": "Complete a boss quest",
            "icon": "🔥",
            "exp_reward": 300
        }
    ]
    
    for achievement_data in achievements:
        # Check if achievement already exists
        existing = db.query(models.Achievement).filter_by(name=achievement_data["name"]).first()
        if not existing:
            achievement = models.Achievement(**achievement_data)
            db.add(achievement)
    
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