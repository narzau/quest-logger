# app/api/routes/google_auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import HTMLResponse

from app.api import deps
from app import models
from app.services.google_calendar_service import GoogleCalendarService
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


# HTML Templates
def get_success_page():
    """Generate success HTML page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Calendar Connected</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
            .success { color: green; font-weight: bold; }
            .message { margin: 20px; }
            .button { background-color: #4CAF50; border: none; color: white; padding: 10px 20px; 
                     text-align: center; text-decoration: none; display: inline-block; 
                     font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h2 class="success">Google Calendar Successfully Connected!</h2>
        <p class="message">You can now create quests with Google Calendar integration.</p>
        <p>You can close this window and return to the app.</p>
        <button class="button" onclick="window.close()">Close Window</button>
    </body>
    </html>
    """


def get_error_page(error_message):
    """Generate error HTML page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connection Error</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
            .error {{ color: red; font-weight: bold; }}
            .message {{ margin: 20px; }}
            .button {{ background-color: #f44336; border: none; color: white; padding: 10px 20px; 
                     text-align: center; text-decoration: none; display: inline-block; 
                     font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h2 class="error">Google Calendar Connection Failed</h2>
        <p class="message">Error: {error_message}</p>
        <p>Please try again or contact support if the problem persists.</p>
        <button class="button" onclick="window.close()">Close Window</button>
    </body>
    </html>
    """


@router.get("/authorize")
def authorize_google(
    current_user: models.User = Depends(deps.get_current_active_user),
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service)
):
    """Start the Google OAuth flow."""
    try:
        # Use the service to start OAuth flow
        result = calendar_service.start_oauth_flow(current_user.id)
        return result
    except Exception as e:
        logger.error(f"Error initiating Google OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback", response_class=HTMLResponse)
async def google_auth_callback(
    state: str = None,
    code: str = None,
    error: str = None,
):
    """
    Public OAuth callback endpoint - receives Google's redirect.
    """
    if error:
        return get_error_page(f"Authorization denied: {error}")

    if not code or not state:
        return get_error_page("Missing required parameters")
    # Create a secure form that will post to the complete endpoint
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Completing Google Authorization</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
            .message {{ margin: 20px; }}
        </style>
    </head>
    <body>
        <h2>Completing Google Calendar Authorization</h2>
        <p class="message">Please wait, completing the connection...</p>
        
        <form id="oauth-form" method="POST" action="/api/v1/auth/google/complete">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="code" value="{code}">
        </form>
        
        <script>
            // Submit the form automatically
            document.addEventListener('DOMContentLoaded', function() {{
                // Small delay to ensure the page renders first
                setTimeout(() => document.getElementById('oauth-form').submit(), 1000);
            }});
        </script>
    </body>
    </html>
    """


@router.post("/complete", response_class=HTMLResponse)
async def complete_google_auth(
    request: Request,
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service)
):
    """Complete the OAuth flow by exchanging the code for tokens."""
    try:
        # Extract data from form submission
        form_data = await request.form()
        state = form_data.get("state")
        code = form_data.get("code")

        if not state or not code:
            return get_error_page("Missing required parameters")

        # Use the service to complete OAuth flow
        calendar_service.complete_oauth_flow(state, code)

        return get_success_page()
    except Exception as e:
        logger.error(f"Error completing Google OAuth: {e}")
        return get_error_page(str(e))


@router.get("/calendars")
def list_google_calendars(
    current_user: models.User = Depends(deps.get_current_active_user),
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service)
):
    """List user's available Google Calendars."""
    try:
        calendars = calendar_service.list_available_calendars(current_user.id)

        # Get the integration to determine selected calendar
        integration = calendar_service.get_active_integration(current_user.id)
        selected_calendar_id = (
            integration.selected_calendar_id if integration else "primary"
        )

        return {"calendars": calendars, "selected_calendar_id": selected_calendar_id}
    except Exception as e:
        logger.error(f"Error listing calendars: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calendars/select")
def select_google_calendar(
    calendar_data: dict = Body(...),
    current_user: models.User = Depends(deps.get_current_active_user),
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service)
):
    """Select a Google Calendar for creating quest events."""
    try:
        calendar_id = calendar_data.get("calendar_id")
        if not calendar_id:
            raise HTTPException(status_code=400, detail="Calendar ID is required")

        result = calendar_service.select_calendar(current_user.id, calendar_id)

        return result
    except Exception as e:
        logger.error(f"Error selecting calendar: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
def get_google_auth_status(
    current_user: models.User = Depends(deps.get_current_active_user),
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service),
):
    """Check Google Calendar connection status."""
    integration = calendar_service.get_integration(current_user.id)

    if not integration or not integration.is_active:
        return {
            "connected": False,
            "status": "not_connected",
            "message": "Not connected to Google Calendar",
        }

    # Check if token is expired
    is_expired = integration.token_expiry and integration.token_expiry < datetime.now()

    if is_expired:
        # Try to refresh the token
        success = calendar_service.refresh_tokens(integration)
        if not success:
            return {
                "connected": False,
                "status": "expired",
                "message": "Token expired and refresh failed",
                "last_connected": integration.updated_at.isoformat()
                if hasattr(integration, "updated_at") and integration.updated_at
                else None,
            }

    # Token is valid
    return {
        "connected": True,
        "status": "connected",
        "message": "Connected to Google Calendar",
        "calendar_id": integration.selected_calendar_id,
        "calendar_name": integration.selected_calendar_name,
        "expires_at": integration.token_expiry.isoformat()
        if integration.token_expiry
        else None,
    }


@router.delete("/disconnect")
def disconnect_google_calendar(
    current_user: models.User = Depends(deps.get_current_active_user),
    calendar_service: GoogleCalendarService = Depends(deps.get_calendar_service),
    
):
    """Disconnect Google Calendar integration."""
    success = calendar_service.disconnect(current_user.id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar integration not found or already disconnected",
        )

    return {
        "success": True,
        "message": "Google Calendar integration disconnected successfully",
    }
