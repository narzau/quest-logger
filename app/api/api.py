# app/api/api.py
from fastapi import APIRouter

from app.api.routes import (
    login,
    users,
    quests,
    achievements,
    google_auth,
    notes,
    subscription,
    time_tracking,
    public,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(quests.router, prefix="/quests", tags=["quests"])
api_router.include_router(
    achievements.router, prefix="/achievements", tags=["achievements"]
)
api_router.include_router(
    google_auth.router, prefix="/auth/google", tags=["google_auth"]
)
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(
    subscription.router, prefix="/subscription", tags=["subscription"]
)
api_router.include_router(
    time_tracking.router, prefix="/time-tracking", tags=["time_tracking"]
)
api_router.include_router(
    public.router, prefix="/public", tags=["public"]
)
