"""
Service registry module.

This module registers all services with the dependency injection system.
"""
from sqlalchemy.orm import Session

# Avoid circular imports by using a late import inside the function
# from app.utils.dependencies import register_service

# Import all service classes
from app.services.note_service import NoteService
from app.services.quest_service import QuestService
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.services.achievement_service import AchievementService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.progression_service import ProgressionService
from app.services.time_tracking_service import TimeTrackingService

def register_services():
    """Register all services with the dependency injection system."""
    # Import register_service inside the function to avoid circular imports
    from app.utils.dependencies import register_service

    # Register each service with its factory function
    register_service(NoteService, lambda db: NoteService(db))
    register_service(QuestService, lambda db: QuestService(db))
    register_service(SubscriptionService, lambda db: SubscriptionService(db))
    register_service(UserService, lambda db: UserService(db))
    register_service(AchievementService, lambda db: AchievementService(db))
    register_service(GoogleCalendarService, lambda db: GoogleCalendarService(db))
    register_service(ProgressionService, lambda db: ProgressionService(db))
    register_service(TimeTrackingService, lambda db: TimeTrackingService(db))
