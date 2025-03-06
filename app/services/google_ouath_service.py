# app/services/google_oauth_service.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request  # Changed import
from googleapiclient.discovery import build
from app.core.config import settings
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app import models

import json
import os
import tempfile
import logging

logger = logging.getLogger(__name__)


def create_oauth_flow():
    """Create OAuth flow for Google Calendar using environment variable JSON."""
    if not settings.GOOGLE_CLIENT_SECRETS_JSON:
        logger.error("No Google OAuth credentials available in environment")
        raise ValueError("GOOGLE_CLIENT_SECRETS_JSON environment variable is not set")

    logger.info("Creating OAuth flow from environment variable")
    try:
        # Create a temporary file with the JSON content
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, "w") as tmp:
                # Write the JSON string to the temp file
                tmp.write(settings.GOOGLE_CLIENT_SECRETS_JSON)

            # Create flow from the temporary file
            return Flow.from_client_secrets_file(
                path,
                scopes=["https://www.googleapis.com/auth/calendar"],
                redirect_uri=f"{settings.SERVER_HOST}{settings.API_V1_STR}/auth/google/callback",
            )
        finally:
            # Clean up the temp file
            os.unlink(path)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in GOOGLE_CLIENT_SECRETS_JSON: {e}")
        raise ValueError("Invalid Google OAuth credentials JSON") from e
    except Exception as e:
        logger.error(f"Error creating OAuth flow from JSON string: {e}")
        raise


def get_google_credentials(user: models.User, db: Session = None):
    """Get Google OAuth credentials for a user, refreshing if needed."""
    if not user.google_token:
        return None

    # Check if token is expired and needs refresh
    token_expired = (
        user.google_token_expiry and user.google_token_expiry < datetime.utcnow()
    )

    if token_expired and db and user.google_refresh_token:
        success = refresh_google_token(db, user)
        if not success:
            return None
    elif token_expired:
        logger.warning(f"Token expired for user {user.id} but no DB session to refresh")
        return None

    # Extract client ID and secret from the JSON
    try:
        client_secrets = json.loads(settings.GOOGLE_CLIENT_SECRETS_JSON)
        web_config = client_secrets.get("web", {})
        client_id = web_config.get("client_id")
        client_secret = web_config.get("client_secret")

        if not client_id or not client_secret:
            logger.error(
                "Missing client_id or client_secret in GOOGLE_CLIENT_SECRETS_JSON"
            )
            return None

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"Error parsing client secrets JSON: {e}")
        return None

    return Credentials(
        token=user.google_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )


def refresh_google_token(db: Session, user: models.User):
    """Refresh an expired Google OAuth token."""
    if not user.google_refresh_token:
        logger.warning(f"No refresh token available for user {user.id}")
        return False

    try:
        # Extract client ID and secret from the JSON
        client_secrets = json.loads(settings.GOOGLE_CLIENT_SECRETS_JSON)
        web_config = client_secrets.get("web", {})
        client_id = web_config.get("client_id")
        client_secret = web_config.get("client_secret")

        if not client_id or not client_secret:
            logger.error(
                "Missing client_id or client_secret in GOOGLE_CLIENT_SECRETS_JSON"
            )
            return False

        # Create credentials with refresh token
        credentials = Credentials(
            token=None,  # Token is expired or missing
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )

        credentials.refresh(Request())

        user.google_token = credentials.token
        if isinstance(credentials.expiry, datetime):
            user.google_token_expiry = credentials.expiry
        elif isinstance(credentials.expiry, (int, float)):
            user.google_token_expiry = datetime.fromtimestamp(credentials.expiry)
        else:
            logger.warning(
                f"Unexpected type for credentials.expiry: {type(credentials.expiry)}"
            )
            user.google_token_expiry = datetime.utcnow() + timedelta(hours=1)
        db.add(user)
        db.commit()

        logger.info(f"Successfully refreshed Google token for user {user.id}")
        return True
    except Exception as e:
        logger.error(f"Error refreshing token for user {user.id}: {e}")
        return False


def create_calendar_service(credentials):
    """Create a Google Calendar service."""
    return build("calendar", "v3", credentials=credentials)
