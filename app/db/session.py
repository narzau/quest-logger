"""
Database session management utilities.

This file provides database connection functionality for the application.
"""

from typing import Generator

# Re-export SessionLocal from base
from app.db.base import SessionLocal, Base, engine


def get_db() -> Generator:
    """
    Get a database session.

    Yields:
        SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
