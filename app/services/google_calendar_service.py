# app/services/google_calendar_service.py
import json
from datetime import datetime, timedelta
from app.services.google_ouath_service import (
    get_google_credentials,
    create_calendar_service,
)
from sqlalchemy.orm import Session
from app import models
import logging

logger = logging.getLogger(__name__)


def create_calendar_event(db: Session, user: models.User, quest: models.Quest):
    """Create a Google Calendar event for a quest."""
    if not user.google_token:
        logger.warning(f"User {user.id} has no Google token")
        return None

    credentials = get_google_credentials(user, db)
    if not credentials:
        logger.warning(f"Could not get valid credentials for user {user.id}")
        return None

    service = create_calendar_service(credentials)

    # Set end time to 1 hour after due date or current time if no due date
    end_time = None
    start_time = None

    if quest.due_date:
        start_time = quest.due_date
        end_time = quest.due_date + timedelta(hours=1)
    else:
        # If no due date, use current time + 1 hour
        start_time = datetime.datetime.utcnow()
        end_time = start_time + timedelta(hours=1)

    # Format times as RFC3339 strings
    start_time_str = start_time.isoformat()
    end_time_str = end_time.isoformat()

    # Add timezone if not present
    if "Z" not in start_time_str and "+" not in start_time_str:
        start_time_str += "Z"
    if "Z" not in end_time_str and "+" not in end_time_str:
        end_time_str += "Z"

    # Create event details with improved visibility
    event = {
        "summary": f"{quest.title}",
        "description": quest.description or "",
        "start": {
            "dateTime": start_time_str,
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time_str,
            "timeZone": "UTC",
        },
        "visibility": "public",
        "transparency": "opaque",  # Show as busy
        "status": "confirmed",
        "reminders": {"useDefault": True},
    }

    try:
        # Log the event being sent to Google
        logger.info(f"Creating calendar event: {json.dumps(event)}")

        # Add event to primary calendar
        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        # Log the created event response
        logger.info(f"Created event response: {json.dumps(created_event)}")

        # Get direct URL to the event
        event_id = created_event.get("id")
        html_link = created_event.get("htmlLink", "")

        # Log direct access information
        logger.info(f"Event created with ID: {event_id}")
        logger.info(f"Direct event link: {html_link}")

        # Update quest with calendar event ID
        quest.google_calendar_event_id = event_id
        db.add(quest)
        db.commit()

        # Verify the event exists by getting it back
        try:
            verification = (
                service.events().get(calendarId="primary", eventId=event_id).execute()
            )
            logger.info(f"Event verification successful: {verification.get('status')}")
        except Exception as e:
            logger.error(f"Event verification failed: {e}")

        return event_id
    except Exception as e:
        logger.error(f"Error creating Google Calendar event: {e}", exc_info=True)
        return None


# Add a utility function to get a direct link to the event
def get_calendar_event_link(db: Session, user: models.User, quest_id: int):
    """Get a direct link to the Google Calendar event for a quest."""
    quest = db.query(models.Quest).filter(models.Quest.id == quest_id).first()
    if not quest or not quest.google_calendar_event_id:
        return None

    try:
        credentials = get_google_credentials(user)
        if not credentials:
            return None

        service = create_calendar_service(credentials)
        event = (
            service.events()
            .get(calendarId="primary", eventId=quest.google_calendar_event_id)
            .execute()
        )
        return event.get("htmlLink")
    except Exception as e:
        logger.error(f"Error getting calendar event link: {e}")
        return None


def update_calendar_event(db: Session, user: models.User, quest: models.Quest):
    """Update a Google Calendar event for a quest."""
    if not user.google_token or not quest.google_calendar_event_id:
        return None

    credentials = get_google_credentials(user)
    if not credentials:
        return None

    service = create_calendar_service(credentials)

    try:
        # Get existing event
        event = (
            service.events()
            .get(calendarId="primary", eventId=quest.google_calendar_event_id)
            .execute()
        )

        # Update event details
        event["summary"] = f"Quest: {quest.title}"
        event["description"] = quest.description or ""

        if quest.due_date:
            event["start"] = {
                "dateTime": quest.due_date.isoformat(),
                "timeZone": "UTC",
            }
            event["end"] = {
                "dateTime": (quest.due_date + timedelta(hours=1)).isoformat(),
                "timeZone": "UTC",
            }

        # Update event in calendar
        updated_event = (
            service.events()
            .update(
                calendarId="primary", eventId=quest.google_calendar_event_id, body=event
            )
            .execute()
        )

        return updated_event.get("id")
    except Exception as e:
        logger.error(f"Error updating Google Calendar event: {e}")
        return None


def delete_calendar_event(db: Session, user: models.User, quest: models.Quest):
    """Delete a Google Calendar event for a quest."""
    if not user.google_token or not quest.google_calendar_event_id:
        return False

    credentials = get_google_credentials(user)
    if not credentials:
        return False

    service = create_calendar_service(credentials)

    try:
        # Delete event from calendar
        service.events().delete(
            calendarId="primary", eventId=quest.google_calendar_event_id
        ).execute()

        # Clear event ID from quest
        quest.google_calendar_event_id = None
        db.add(quest)
        db.commit()

        return True
    except Exception as e:
        logger.error(f"Error deleting Google Calendar event: {e}")
        return False
