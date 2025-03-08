# app/services/integration_service.py
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.google_calendar import GoogleCalendarIntegration
from app.models.quest import Quest
from app.repositories.google_calendar_repository import GoogleCalendarRepository
from app.integrations.google.oauth import GoogleOAuthClient
from app.integrations.google.calendar import GoogleCalendarClient
import logging
import secrets

logger = logging.getLogger(__name__)

# Store OAuth states temporarily
# In production, use Redis or another distributed cache
OAUTH_STATES = {}


class GoogleCalendarService:
    """Service for Google Calendar integration operations."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = GoogleCalendarRepository(db)

    def start_oauth_flow(self, user_id: int) -> Dict[str, Any]:
        """Start the Google OAuth flow for a user."""
        try:
            # Create OAuth flow
            flow = GoogleOAuthClient.create_oauth_flow()

            # Generate state token
            state = secrets.token_urlsafe(32)

            # Store state token temporarily
            OAUTH_STATES[state] = user_id

            # Get or create integration record
            integration = self.repository.get_by_user_id(user_id)
            if integration:
                integration.oauth_state = state
                integration.connection_status = "authorizing"
                self.repository.save(integration)
            else:
                integration = GoogleCalendarIntegration(
                    user_id=user_id, oauth_state=state, connection_status="authorizing"
                )
                self.repository.save(integration)

            # Generate authorization URL
            authorization_url, _ = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
                state=state,
            )

            return {"authorization_url": authorization_url}
        except Exception as e:
            logger.error(f"Error initiating Google OAuth flow: {e}")
            raise ValueError(f"Failed to start Google authorization: {str(e)}")

    def complete_oauth_flow(self, state: str, code: str) -> GoogleCalendarIntegration:
        """Complete the OAuth flow with the received code."""
        try:
            # Verify state and get integration
            integration = self.repository.get_by_oauth_state(state)
            if not integration:
                raise ValueError("Invalid state parameter")

            # Also check the temporary state storage
            if state not in OAUTH_STATES or OAUTH_STATES[state] != integration.user_id:
                raise ValueError("State mismatch")

            # Clean up temporary state
            if state in OAUTH_STATES:
                del OAUTH_STATES[state]

            # Exchange code for tokens
            credentials = GoogleOAuthClient.exchange_code(code)

            # Parse expiry time
            token_expiry = GoogleOAuthClient.parse_expiry(credentials.expiry)

            # Update integration with tokens
            integration.access_token = credentials.token
            integration.refresh_token = credentials.refresh_token
            integration.token_expiry = token_expiry
            integration.oauth_state = None  # Clear the state
            integration.connection_status = "connected"
            integration.is_active = True

            # If no calendar is selected, use primary as default
            if not integration.selected_calendar_id:
                integration.selected_calendar_id = "primary"
                integration.selected_calendar_name = "Primary Calendar"

            self.repository.save(integration)
            return integration
        except Exception as e:
            logger.error(f"Error completing OAuth flow: {e}")
            raise ValueError(f"Failed to complete Google authorization: {str(e)}")

    def get_integration(self, user_id: int) -> Optional[GoogleCalendarIntegration]:
        """Get Google Calendar integration for a user."""
        return self.repository.get_by_user_id(user_id)

    def get_active_integration(
        self, user_id: int
    ) -> Optional[GoogleCalendarIntegration]:
        """Get active Google Calendar integration for a user."""
        return self.repository.get_active_by_user_id(user_id)

    def refresh_tokens(self, integration: GoogleCalendarIntegration) -> bool:
        """Refresh OAuth tokens for an integration."""
        try:
            credentials = GoogleOAuthClient.refresh_token(integration)
            if not credentials:
                return False

            # Update integration with new tokens
            integration.access_token = credentials.token
            token_expiry = GoogleOAuthClient.parse_expiry(credentials.expiry)
            integration.token_expiry = token_expiry
            integration.connection_status = "connected"

            self.repository.save(integration)
            return True
        except Exception as e:
            logger.error(f"Error refreshing tokens: {e}")
            return False

    def list_available_calendars(self, user_id: int) -> List[Dict[str, Any]]:
        """List available calendars for a user."""
        integration = self.get_active_integration(user_id)
        if not integration:
            raise ValueError("No active Google Calendar integration found")

        # Check if token is expired
        if integration.token_expiry and integration.token_expiry < datetime.utcnow():
            success = self.refresh_tokens(integration)
            if not success:
                raise ValueError("Failed to refresh expired token")

        # Create calendar client
        calendar_client = GoogleCalendarClient.from_integration(integration)
        if not calendar_client:
            raise ValueError("Failed to create calendar client")

        # List calendars
        calendars = calendar_client.list_calendars()

        # Format response
        result = []
        for calendar in calendars:
            # Only include calendars where the user has sufficient access
            access_role = calendar.get("accessRole", "")
            if access_role in ["owner", "writer"]:
                result.append(
                    {
                        "id": calendar.get("id"),
                        "name": calendar.get("summary", "Unnamed Calendar"),
                        "description": calendar.get("description", ""),
                        "primary": calendar.get("primary", False),
                        "selected": (
                            calendar.get("id") == integration.selected_calendar_id
                        ),
                        "color": calendar.get("backgroundColor", "#9FC6E7"),
                        "access_role": access_role,
                    }
                )

        return result

    def select_calendar(self, user_id: int, calendar_id: str) -> Dict[str, Any]:
        """Select a calendar for a user."""
        integration = self.get_active_integration(user_id)
        if not integration:
            raise ValueError("No active Google Calendar integration found")

        # Check if token is expired
        if integration.token_expiry and integration.token_expiry < datetime.utcnow():
            success = self.refresh_tokens(integration)
            if not success:
                raise ValueError("Failed to refresh expired token")

        # Create calendar client
        calendar_client = GoogleCalendarClient.from_integration(integration)
        if not calendar_client:
            raise ValueError("Failed to create calendar client")

        # Verify the calendar exists and is accessible
        calendar = calendar_client.get_calendar(calendar_id)
        if not calendar:
            raise ValueError(f"Calendar {calendar_id} not found or not accessible")

        # Update integration with selected calendar
        calendar_name = calendar.get("summary", "Selected Calendar")
        integration.selected_calendar_id = calendar_id
        integration.selected_calendar_name = calendar_name
        self.repository.save(integration)

        return {
            "message": f"Calendar '{calendar_name}' selected successfully",
            "calendar_id": calendar_id,
            "calendar_name": calendar_name,
        }

    def create_calendar_event(self, user_id: int, quest: Quest) -> Optional[str]:
        """Create a calendar event for a quest."""
        integration = self.get_active_integration(user_id)
        if not integration:
            logger.warning(
                f"No active Google Calendar integration found for user {user_id}"
            )
            return None

        # Check if token is expired
        if integration.token_expiry and integration.token_expiry < datetime.utcnow():
            success = self.refresh_tokens(integration)
            if not success:
                logger.warning(f"Failed to refresh expired token for user {user_id}")
                return None

        # Create calendar client
        calendar_client = GoogleCalendarClient.from_integration(integration)
        if not calendar_client:
            logger.warning(f"Failed to create calendar client for user {user_id}")
            return None

        # Use selected calendar if available, otherwise use primary
        calendar_id = integration.selected_calendar_id or "primary"

        # Create event
        event = calendar_client.create_event(quest, calendar_id)
        if not event:
            return None

        return event.get("id")

    def update_calendar_event(self, user_id: int, quest: Quest) -> bool:
        """Update a calendar event for a quest."""
        if not quest.google_calendar_event_id:
            return False

        integration = self.get_active_integration(user_id)
        if not integration:
            logger.warning(
                f"No active Google Calendar integration found for user {user_id}"
            )
            return False

        # Check if token is expired
        if integration.token_expiry and integration.token_expiry < datetime.utcnow():
            success = self.refresh_tokens(integration)
            if not success:
                logger.warning(f"Failed to refresh expired token for user {user_id}")
                return False

        # Create calendar client
        calendar_client = GoogleCalendarClient.from_integration(integration)
        if not calendar_client:
            logger.warning(f"Failed to create calendar client for user {user_id}")
            return False

        # Use selected calendar if available, otherwise use primary
        calendar_id = integration.selected_calendar_id or "primary"

        # Update event
        result = calendar_client.update_event(
            quest.google_calendar_event_id, quest, calendar_id
        )
        return result is not None

    def delete_calendar_event(self, user_id: int, quest: Quest) -> bool:
        """Delete a calendar event for a quest."""
        if not quest.google_calendar_event_id:
            return False

        integration = self.get_active_integration(user_id)
        if not integration:
            logger.warning(
                f"No active Google Calendar integration found for user {user_id}"
            )
            return False

        # Check if token is expired
        if integration.token_expiry and integration.token_expiry < datetime.utcnow():
            success = self.refresh_tokens(integration)
            if not success:
                logger.warning(f"Failed to refresh expired token for user {user_id}")
                return False

        # Create calendar client
        calendar_client = GoogleCalendarClient.from_integration(integration)
        if not calendar_client:
            logger.warning(f"Failed to create calendar client for user {user_id}")
            return False

        # Use selected calendar if available, otherwise use primary
        calendar_id = integration.selected_calendar_id or "primary"

        # Delete event
        return calendar_client.delete_event(quest.google_calendar_event_id, calendar_id)

    def disconnect(self, user_id: int) -> bool:
        """Disconnect Google Calendar integration."""
        integration = self.repository.get_by_user_id(user_id)
        if not integration:
            return False

        integration.is_active = False
        integration.connection_status = "disconnected"
        self.repository.save(integration)
        return True
