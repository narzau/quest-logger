from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.base_repository import BaseRepository
from app.models.google_calendar import GoogleCalendarIntegration



class GoogleCalendarRepository(BaseRepository[GoogleCalendarIntegration]):
    """Repository for Google Calendar integrations."""
    
    def __init__(self, db: Session):
        super().__init__(GoogleCalendarIntegration, db)
    
    def get_by_user_id(self, user_id: int) -> Optional[GoogleCalendarIntegration]:
        """Get Google Calendar integration for a specific user."""
        return self.get_by(user_id=user_id)
    
    def get_by_oauth_state(self, state: str) -> Optional[GoogleCalendarIntegration]:
        """Get integration by OAuth state token."""
        return self.get_by(oauth_state=state)
    
    def get_active_by_user_id(self, user_id: int) -> Optional[GoogleCalendarIntegration]:
        """Get active Google Calendar integration for a specific user."""
        return self.db.query(GoogleCalendarIntegration).filter(
            GoogleCalendarIntegration.user_id == user_id,
            GoogleCalendarIntegration.is_active == True
        ).first()
    
    def update_selected_calendar(
        self, 
        integration_id: int, 
        calendar_id: str, 
        calendar_name: str
    ) -> Optional[GoogleCalendarIntegration]:
        """Update the selected calendar for a Google Calendar integration."""
        integration = self.get(integration_id)
        if not integration:
            return None
        
        integration.selected_calendar_id = calendar_id
        integration.selected_calendar_name = calendar_name
        return self.save(integration)
    
    def update_tokens(
        self, 
        integration_id: int, 
        access_token: str, 
        refresh_token: str = None,
        token_expiry = None
    ) -> Optional[GoogleCalendarIntegration]:
        """Update OAuth tokens for a Google Calendar integration."""
        integration = self.get(integration_id)
        if not integration:
            return None
        
        integration.access_token = access_token
        if refresh_token:
            integration.refresh_token = refresh_token
        if token_expiry:
            integration.token_expiry = token_expiry
        
        integration.connection_status = "connected"
        return self.save(integration)