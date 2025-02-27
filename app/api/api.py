# app/api/api.py
from fastapi import APIRouter

from app.api.routes import login, users, quests, achievements

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(quests.router, prefix="/quests", tags=["quests"])
api_router.include_router(achievements.router, prefix="/achievements", tags=["achievements"])