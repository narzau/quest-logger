# app/integrations/google/calendar.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.models.google_calendar import GoogleCalendarIntegration
from app.models.quest import Quest
from app.integrations.google.oauth import GoogleOAuthClient
from datetime import datetime, timedelta

import logging

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Client for Google Calendar API."""

    def __init__(self, credentials: Credentials):
        """Initialize with valid Google OAuth credentials."""
        self.service = build("calendar", "v3", credentials=credentials)

    @classmethod
    def from_integration(cls, integration: GoogleCalendarIntegration):
        """Create a client from a GoogleCalendarIntegration record."""
        credentials = GoogleOAuthClient.get_credentials(integration)
        if not credentials:
            return None

        return cls(credentials)

    def list_calendars(self, max_results=100):
        """List available calendars."""
        try:
            result = self.service.calendarList().list(maxResults=max_results).execute()
            return result.get("items", [])
        except Exception as e:
            logger.error(f"Error listing calendars: {e}")
            return []

    def get_calendar(self, calendar_id="primary"):
        """Get details of a specific calendar."""
        try:
            return self.service.calendars().get(calendarId=calendar_id).execute()
        except Exception as e:
            logger.error(f"Error getting calendar {calendar_id}: {e}")
            return None

    def create_event(self, quest: Quest, calendar_id="primary"):
        """Create a calendar event based on a quest."""
        try:
            # Set end time to 1 hour after due date or current time if no due date
            end_time = None
            start_time = None

            if quest.due_date:
                start_time = quest.due_date
                end_time = quest.due_date + timedelta(hours=1)
            else:
                # If no due date, use current time + 1 hour
                start_time = datetime.utcnow()
                end_time = start_time + timedelta(hours=1)

            # Format times as RFC3339 strings
            start_time_str = start_time.isoformat()
            end_time_str = end_time.isoformat()

            # Add timezone if not present
            if "Z" not in start_time_str and "+" not in start_time_str:
                start_time_str += "Z"
            if "Z" not in end_time_str and "+" not in end_time_str:
                end_time_str += "Z"

            # Create event details
            event = {
                "summary": f"Quest: {quest.title}",
                "description": quest.description or "",
                "start": {
                    "dateTime": start_time_str,
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time_str,
                    "timeZone": "UTC",
                },
                "reminders": {"useDefault": True},
            }

            created_event = (
                self.service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute()
            )
            logger.info(
                f"Created event {created_event.get('id')} in calendar {calendar_id}"
            )
            return created_event
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    def update_event(self, event_id: str, quest: Quest, calendar_id="primary"):
        """Update an existing calendar event based on a quest."""
        try:
            # First retrieve the existing event
            try:
                event = (
                    self.service.events()
                    .get(calendarId=calendar_id, eventId=event_id)
                    .execute()
                )
            except Exception as e:
                # If event not found in the specified calendar, try primary
                if calendar_id != "primary":
                    try:
                        logger.info(
                            f"Event not found in specified calendar, trying primary"
                        )
                        event = (
                            self.service.events()
                            .get(calendarId="primary", eventId=event_id)
                            .execute()
                        )
                        # Update calendar_id for this operation
                        calendar_id = "primary"
                    except Exception as inner_e:
                        logger.error(
                            f"Event not found in primary calendar either: {inner_e}"
                        )
                        return None
                else:
                    logger.error(f"Event not found: {e}")
                    return None

            # Update event details
            event["summary"] = f"Quest: {quest.title}"
            event["description"] = quest.description or ""

            if quest.due_date:
                start_time = quest.due_date
                end_time = quest.due_date + timedelta(hours=1)

                # Format times as RFC3339 strings
                start_time_str = start_time.isoformat()
                end_time_str = end_time.isoformat()

                # Add timezone if not present
                if "Z" not in start_time_str and "+" not in start_time_str:
                    start_time_str += "Z"
                if "Z" not in end_time_str and "+" not in end_time_str:
                    end_time_str += "Z"

                event["start"] = {
                    "dateTime": start_time_str,
                    "timeZone": "UTC",
                }
                event["end"] = {
                    "dateTime": end_time_str,
                    "timeZone": "UTC",
                }

            updated_event = (
                self.service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            logger.info(
                f"Updated event {updated_event.get('id')} in calendar {calendar_id}"
            )
            return updated_event
        except Exception as e:
            logger.error(f"Error updating calendar event: {e}")
            return None

    def delete_event(self, event_id: str, calendar_id="primary"):
        """Delete a calendar event."""
        try:
            try:
                self.service.events().delete(
                    calendarId=calendar_id, eventId=event_id
                ).execute()
            except Exception as e:
                # If not found in specified calendar, try primary
                if calendar_id != "primary":
                    try:
                        logger.info(
                            f"Event not found in specified calendar, trying primary"
                        )
                        self.service.events().delete(
                            calendarId="primary", eventId=event_id
                        ).execute()
                    except Exception as inner_e:
                        logger.error(
                            f"Event not found in primary calendar either: {inner_e}"
                        )
                        return False
                else:
                    logger.error(f"Event not found: {e}")
                    return False

            logger.info(f"Deleted event {event_id} from calendar {calendar_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting calendar event: {e}")
            return False

    def list_events(self, calendar_id="primary", max_results=10):
        """List upcoming events in a calendar."""
        try:
            now = datetime.utcnow().isoformat() + "Z"
            events_result = (
                self.service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return events_result.get("items", [])
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            return []
