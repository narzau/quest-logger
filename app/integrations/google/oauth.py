# app/integrations/google/oauth.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from app.core.config import settings
from app.models.google_calendar import GoogleCalendarIntegration
from datetime import datetime, timedelta, timezone

import json
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

class GoogleOAuthClient:
    """Client for Google OAuth authentication."""
    
    @staticmethod
    def create_oauth_flow(redirect_uri: str = None):
        """Create OAuth flow for Google Calendar using environment variable JSON."""
        if not settings.GOOGLE_CLIENT_SECRETS_JSON:
            logger.error("No Google OAuth credentials available in environment")
            raise ValueError("GOOGLE_CLIENT_SECRETS_JSON environment variable is not set")
        
        logger.info("Creating OAuth flow from environment variable")
        try:
            # If no redirect URI specified, use the default from settings
            if not redirect_uri:
                redirect_uri = f"{settings.SERVER_HOST}{settings.API_V1_STR}/auth/google/callback"
            
            # Create a temporary file with the JSON content
            fd, path = tempfile.mkstemp()
            try:
                with os.fdopen(fd, 'w') as tmp:
                    # Write the JSON string to the temp file
                    tmp.write(settings.GOOGLE_CLIENT_SECRETS_JSON)
                
                # Create flow from the temporary file
                return Flow.from_client_secrets_file(
                    path,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                    redirect_uri=redirect_uri
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
    
    @staticmethod
    def exchange_code(code: str):
        """Exchange authorization code for tokens."""
        flow = GoogleOAuthClient.create_oauth_flow()
        flow.fetch_token(code=code)
        return flow.credentials
    
    @staticmethod
    def get_client_config():
        """Extract client ID and secret from the environment."""
        try:
            client_secrets = json.loads(settings.GOOGLE_CLIENT_SECRETS_JSON)
            web_config = client_secrets.get('web', {})
            client_id = web_config.get('client_id')
            client_secret = web_config.get('client_secret')
            
            if not client_id or not client_secret:
                logger.error("Missing client_id or client_secret in GOOGLE_CLIENT_SECRETS_JSON")
                return None, None
                
            return client_id, client_secret
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error parsing client secrets JSON: {e}")
            return None, None
    
    @staticmethod
    def get_credentials(integration: GoogleCalendarIntegration):
        """Create Google OAuth credentials from an integration record."""
        if not integration or not integration.access_token:
            return None
        
        client_id, client_secret = GoogleOAuthClient.get_client_config()
        if not client_id or not client_secret:
            return None
            
        return Credentials(
            token=integration.access_token,
            refresh_token=integration.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
    
    @staticmethod
    def refresh_token(integration: GoogleCalendarIntegration):
        """Refresh an expired OAuth token."""
        if not integration.refresh_token:
            logger.warning(f"No refresh token available for integration {integration.id}")
            return None
            
        client_id, client_secret = GoogleOAuthClient.get_client_config()
        if not client_id or not client_secret:
            return None
        
        try:
            # Create credentials with refresh token
            credentials = Credentials(
                token=None,  # Token is expired or missing
                refresh_token=integration.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/calendar"]
            )
            
            # Refresh the token
            request = Request()
            credentials.refresh(request)
            
            # Return refreshed credentials
            return credentials
        except Exception as e:
            logger.error(f"Error refreshing token for integration {integration.id}: {e}")
            return None
    
    @staticmethod
    def parse_expiry(expiry):
        """Parse expiry value into a datetime object."""
        if isinstance(expiry, datetime):
            return expiry
        elif isinstance(expiry, (int, float)):
            return datetime.fromtimestamp(expiry)
        else:
            logger.warning(f"Unexpected type for expiry: {type(expiry)}")
            return datetime.now(timezone.utc) + timedelta(hours=1)