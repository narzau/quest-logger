# app/repositories/user_repository.py
from typing import Optional
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import get_password_hash


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[models.User]:
        """Get user by ID."""
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[models.User]:
        """Get user by ID."""
        return self.db.query(models.User).filter(models.User.email == email).first()

    def update(self, user: models.User) -> models.User:
        """Update user and persist changes."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_me(
        self, user: models.User, update_data: schemas.UserUpdate
    ) -> models.User:
        """Update user and persist changes."""
        update_user_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_user_dict.items():
            if hasattr(user, field):
                setattr(user, field, value)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_user(self, create_data: schemas.UserCreate) -> models.User:
        user = models.User(
            email=create_data.email,
            username=create_data.username,
            hashed_password=get_password_hash(create_data.password),
            level=1,
            experience=0,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
