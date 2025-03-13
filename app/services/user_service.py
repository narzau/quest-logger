# app/services/user_service.py
from typing import Optional, Tuple
from sqlalchemy.orm import Session
import logging

from app import models, schemas
from app.repositories.user_repository import UserRepository
from app.core.exceptions import DuplicateResourceException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def get_user_by_email(self, email: str) -> Optional[models.User]:
        """Get user by ID."""
        return self.repository.get_by_email(email)

    def get_user_by_id(self, user_id: int) -> Optional[models.User]:
        """Get user by ID."""
        return self.repository.get_by_id(user_id)

    def add_experience(self, user_id: int, exp_amount: int) -> Optional[models.User]:
        """Add experience to a user."""
        if exp_amount <= 0:
            logger.warning(
                f"Attempted to add non-positive XP amount: {exp_amount} to user {user_id}"
            )
            return self.get_user_by_id(user_id)

        logger.info(f"Adding {exp_amount} experience to user {user_id}")
        user = self.repository.get_by_id(user_id)
        if not user:
            return None

        # Log before state
        logger.info(f"User {user_id} before XP: {user.experience}")

        # Add experience
        user.experience += exp_amount

        # Log after state
        logger.info(f"User {user_id} after XP: {user.experience} (+{exp_amount})")

        return self.repository.update(user)

    def calculate_xp_for_next_level(self, level: int) -> int:
        """
        Calculate XP required for the next level using RPG-style formula.
        Uses a common formula: 100 * (level^1.5)
        """
        return int(100 * (level**1.5))

    def check_and_apply_level_up(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user has enough XP to level up and apply levels if eligible.
        Returns (did_level_up, new_level)
        """
        user = self.repository.get_by_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found during level check")
            return False, 0

        original_level = user.level

        # Check for multiple level-ups
        while True:
            xp_needed = self.calculate_xp_for_next_level(user.level)
            if user.experience >= xp_needed:
                user.level += 1
                logger.info(f"User {user_id} leveled up to {user.level}")
            else:
                break

        if user.level > original_level:
            # Update user if they leveled up
            self.repository.update(user)
            return True, user.level

        return False, original_level

    def update(self, user: models.User):
        return self.repository.update(user)

    def update_me(self, user_id: int, update_data: schemas.UserUpdate):
        user = self.repository.get_by_id(user_id)
        if not user:
            raise ResourceNotFoundException(f"User with ID {user_id} not found")
        return self.repository.update_me(user, update_data)

    def create_user(self, create_data: schemas.UserCreate):
        existing_email = self.repository.get_by_email(create_data.email)
        if existing_email:
            raise DuplicateResourceException(
                f"User with email {create_data.email} already exists"
            )

        return self.repository.create_user(create_data)
