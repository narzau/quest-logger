# app/main.py
import asyncio
import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.api.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.error_handlers import register_exception_handlers
from app.core.middleware import register_middlewares
from app.db.base import SessionLocal
from app.services.subscription_service import SubscriptionService
from app.services import register_services

# Set up the logger at the start
logger = setup_logging()


# Background task for checking expired trials
async def check_expired_trials():
    while True:
        try:
            # Create a new database session
            db = SessionLocal()
            try:
                # Check and update expired trials
                subscription_service = SubscriptionService(db)
                updated_count = (
                    await subscription_service.check_and_update_expired_trials()
                )
                if updated_count > 0:
                    logger.info(f"Updated {updated_count} expired trial subscriptions")
            finally:
                db.close()

            # Wait for 1 hour before checking again
            await asyncio.sleep(3600)  # 1 hour in seconds
        except Exception as e:
            logger.error(f"Error in background task: {str(e)}", exc_info=True)
            # Wait for a minute before retrying
            await asyncio.sleep(60)


# Context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log application startup
    logger.info(f"Starting Quest Logger API {app.version}")

    # Register services
    register_services()
    logger.info("Services registered")

    # Start background tasks on startup
    background_task = asyncio.create_task(check_expired_trials())

    yield

    # Cancel background tasks on shutdown
    logger.info("Shutting down application and background tasks")
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        logger.info("Background tasks cancelled successfully")


app = FastAPI(
    title="Quest Logger API",
    description="API for a gamified task tracking app with advanced AI features",
    version="0.2.0",
    lifespan=lifespan,
)

# Register custom exception handlers
register_exception_handlers(app)

# Register middleware
register_middlewares(app)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    allowed_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    logger.info(f"Setting up CORS with allowed origins: {allowed_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"message": "Welcome to the Quest Logger API"}


# needed for vercel
def create_app():
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
