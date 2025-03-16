"""
Shared fixtures and configuration for all tests.
"""
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

# Override environment settings for testing
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "testsecretkey"
os.environ["BACKEND_CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["STRIPE_API_KEY"] = "sk_test_key"
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "sqlite:///./test.db")

from app.main import app
from app.db.base import Base, engine
from app.db.session import get_db
from app.api.deps import get_current_user, get_note_service, get_subscription_service
from app.services.note_service import NoteService
from app.services.subscription_service import SubscriptionService
from app.repositories.user_repository import UserRepository
from app.models.user import User


# Create a test database configuration
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./test.db"
)

# Use in-memory SQLite for testing if no environment variable is set
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Test fixtures for the database
@pytest.fixture
def db():
    """
    Create a fresh database for each test.
    """
    # Create the database tables
    Base.metadata.create_all(bind=engine)
    
    # Create a database session
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        
    # Drop tables after the test
    Base.metadata.drop_all(bind=engine)


# Test users
@pytest.fixture
def test_user():
    """Create a test user data."""
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "fakehashed_password",
        "is_active": True
    }


@pytest.fixture
def create_test_user(db, test_user):
    """Create a test user in the database."""
    user_repo = UserRepository(db)
    user = User(
        id=test_user["id"],
        username=test_user["username"],
        email=test_user["email"],
        hashed_password=test_user["hashed_password"],
        is_active=test_user["is_active"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Test client with authentication
@pytest.fixture
def client():
    """Return a TestClient for making requests to the app."""
    # Keep the API prefix for testing
    from app.core.config import settings
    
    # Store the original prefix
    original_prefix = settings.API_V1_STR
    
    # Keep the API prefix for testing
    settings.API_V1_STR = "/api/v1"
    
    # Create the test client
    test_client = TestClient(app)
    
    yield test_client
    
    # Restore the original prefix after the test
    settings.API_V1_STR = original_prefix


@pytest.fixture
def authorized_client(client, test_user, db):
    """Return a TestClient that skips the authentication."""
    # Create a User object from the test_user dictionary
    user = User(
        id=test_user["id"],
        username=test_user["username"],
        email=test_user["email"],
        hashed_password=test_user["hashed_password"],
        is_active=test_user["is_active"]
    )
    
    # Override the dependency to skip authentication
    def override_get_current_user():
        return user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Use the test database
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Keep the app's API prefix as '/api/v1' for testing
    from app.core.config import settings
    settings.API_V1_STR = "/api/v1"  # Keep the API prefix for testing
    
    yield client
    
    # Reset overrides after test
    app.dependency_overrides = {}


# Service mocks
@pytest.fixture
def mock_note_service():
    """Mock note service for testing."""
    service = MagicMock(spec=NoteService)
    service.process_audio_upload = AsyncMock()
    service.export_note = AsyncMock()
    service.get_user_notes = AsyncMock()
    service.get_user_note = AsyncMock()
    
    # Override the dependency
    app.dependency_overrides[get_note_service] = lambda: service
    
    yield service
    
    # Reset after test
    if get_note_service in app.dependency_overrides:
        del app.dependency_overrides[get_note_service]


@pytest.fixture
def mock_subscription_service():
    """Mock subscription service for testing."""
    service = MagicMock(spec=SubscriptionService)
    service.get_user_subscription = AsyncMock()
    service.update_subscription = AsyncMock()
    service.create_checkout_session = AsyncMock()
    
    # Override the dependency
    app.dependency_overrides[get_subscription_service] = lambda: service
    
    yield service
    
    # Reset after test
    if get_subscription_service in app.dependency_overrides:
        del app.dependency_overrides[get_subscription_service] 