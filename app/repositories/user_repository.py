# app/repositories/user_repository.py
from typing import Optional
from sqlalchemy.orm import Session

from app import models

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> Optional[models.User]:
        """Get user by ID."""
        return self.db.query(models.User).filter(models.User.id == user_id).first()
    
    def update(self, user: models.User) -> models.User:
        """Update user and persist changes."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user