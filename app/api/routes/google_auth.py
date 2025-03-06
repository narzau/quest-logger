# Update app/api/routes/google_auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from datetime import datetime
from sqlalchemy.orm import Session
from app.api import deps
from app import models
from app.services.google_ouath_service import (
    create_oauth_flow,
    refresh_google_token,
    get_google_credentials,
    create_calendar_service,
)
import logging
import secrets

router = APIRouter()
logger = logging.getLogger(__name__)

STATE_STORE = {}


@router.get("/authorize")
def authorize_google(
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """Start the Google OAuth flow."""
    try:
        flow = create_oauth_flow()

        # Generate state and store it with user ID
        state = secrets.token_urlsafe(32)
        STATE_STORE[state] = current_user.id

        authorization_url, flow_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,  # Pass our custom state
        )

        # Store state in user model as backup
        current_user.google_oauth_state = state
        db.add(current_user)
        db.commit()

        return {"authorization_url": authorization_url}
    except Exception as e:
        logger.error(f"Error initiating Google OAuth flow: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to start Google authorization"
        )


@router.get("/callback")
async def google_auth_callback(
    request: Request,
    db: Session = Depends(deps.get_db),
    state: str = None,
    code: str = None,
    error: str = None,
):
    """Handle the Google OAuth callback without requiring authentication."""
    try:
        # Check for error parameter
        if error:
            logger.error(f"Google OAuth error: {error}")
            return RedirectResponse(url="/oauth-error?error=" + error)

        # Validate parameters
        if not code:
            logger.error("No authorization code in callback")
            return RedirectResponse(url="/oauth-error?error=no_code")

        if not state or state not in STATE_STORE:
            logger.error("Invalid or missing state parameter")
            return RedirectResponse(url="/oauth-error?error=invalid_state")

        # Get user ID from state
        user_id = STATE_STORE.pop(state)  # Remove state after use

        # Get user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            logger.error(f"User not found for ID: {user_id}")
            return RedirectResponse(url="/oauth-error?error=user_not_found")

        # Verify state matches what we stored in the user record
        if user.google_oauth_state != state:
            logger.error(f"State mismatch: {state} vs {user.google_oauth_state}")
            return RedirectResponse(url="/oauth-error?error=state_mismatch")

        # Exchange code for tokens
        flow = create_oauth_flow()
        flow.fetch_token(code=code)

        # Get credentials
        credentials = flow.credentials

        # Store tokens in the database
        user.google_token = credentials.token
        user.google_refresh_token = credentials.refresh_token

        # Fix: Handle expiry correctly depending on type
        if isinstance(credentials.expiry, datetime.datetime):
            # Already a datetime object, use directly
            user.google_token_expiry = credentials.expiry
        elif isinstance(credentials.expiry, (int, float)):
            # It's a timestamp (integer/float), convert to datetime
            user.google_token_expiry = datetime.datetime.fromtimestamp(
                credentials.expiry
            )
        else:
            # Unexpected type, use current time + 1 hour as default
            logger.warning(
                f"Unexpected type for credentials.expiry: {type(credentials.expiry)}"
            )
            user.google_token_expiry = datetime.datetime.now() + datetime.timedelta(
                hours=1
            )

        user.google_oauth_state = None  # Clear the state

        db.add(user)
        db.commit()

        # Redirect to success page
        return RedirectResponse(url="/oauth-success")
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}")
        return RedirectResponse(url=f"/oauth-error?error={str(e)}")


# Add simple success/error HTML endpoints for better user experience


@router.get("/oauth-success", include_in_schema=False)
async def oauth_success():
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>OAuth Success</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .success { color: green; }
            </style>
        </head>
        <body>
            <h1 class="success">Google Calendar Connected Successfully!</h1>
            <p>You can now close this window and return to the application.</p>
        </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")


@router.get("/oauth-error", include_in_schema=False)
async def oauth_error(error: str = "unknown_error"):
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>OAuth Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h1 class="error">Google Calendar Connection Failed</h1>
            <p>Error: {error}</p>
            <p>Please close this window and try again.</p>
        </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")


@router.delete("/disconnect")
def disconnect_google(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """Disconnect Google Calendar integration."""
    current_user.google_token = None
    current_user.google_refresh_token = None
    current_user.google_token_expiry = None
    current_user.google_oauth_state = None

    db.add(current_user)
    db.commit()

    return {"success": True, "message": "Google Calendar disconnected successfully"}


@router.get("/status")
def google_connection_status(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """Check Google Calendar connection status and health."""
    if not current_user.google_token:
        return {
            "connected": False,
            "status": "not_connected",
            "message": "Not connected to Google Calendar",
        }

    # Check if token is expired
    if (
        current_user.google_token_expiry
        and current_user.google_token_expiry < datetime.now()
    ):
        # Try to refresh token
        if current_user.google_refresh_token:
            success = refresh_google_token(db, current_user)
            if not success:
                return {
                    "connected": False,
                    "status": "refresh_failed",
                    "message": "Token expired and refresh failed",
                    "expired_at": current_user.google_token_expiry.isoformat(),
                }
        else:
            return {
                "connected": False,
                "status": "expired_no_refresh",
                "message": "Token expired and no refresh token available",
                "expired_at": current_user.google_token_expiry.isoformat(),
            }

    # Test connection with a simple API call
    try:
        credentials = get_google_credentials(current_user, db)
        service = create_calendar_service(credentials)

        # Get calendar list (lightweight test)
        calendar_list = service.calendarList().list(maxResults=1).execute()

        return {
            "connected": True,
            "status": "active",
            "message": "Google Calendar connection is active",
            "expires_at": current_user.google_token_expiry.isoformat()
            if current_user.google_token_expiry
            else None,
            "calendar_count": len(calendar_list.get("items", [])),
        }
    except Exception as e:
        logger.error(f"Error testing Google connection: {e}")
        return {
            "connected": False,
            "status": "error",
            "message": f"Error testing connection: {str(e)}",
        }
