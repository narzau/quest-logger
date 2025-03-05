# app/api/api.py
from fastapi import APIRouter

from app.api.routes import (
    login,
    users,
    quests,
    achievements,
    voice,
    llm_features,
    google_auth,
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

if settings.ENABLE_LLM_FEATURES:
    api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
    api_router.include_router(llm_features.router, prefix="/llm", tags=["llm"])
