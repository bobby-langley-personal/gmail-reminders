"""
Google Calendar Client

Creates calendar events with multiple reminders from extracted appointment data.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Reminders in minutes before the event.
# Google Calendar enforces a maximum of 5 reminders per event.
REMINDER_MINUTES = [
    15,       # 15 minutes
    60,       # 1 hour
    1440,     # 1 day
    10080,    # 1 week
    20160,    # 2 weeks
]


class CalendarClient:
    """Creates Google Calendar events with reminders."""

    def __init__(self, credentials):
        """
        Args:
            credentials: Google OAuth credentials object (from GmailClient)
        """
        self.service = build('calendar', 'v3', credentials=credentials)
        logger.info("Google Calendar client initialized")

    def create_event(self, appointment: Dict, email: Dict) -> Optional[str]:
        """
        Create a calendar event from extracted appointment data.

        Args:
            appointment: Dict from AppointmentExtractor.extract()
            email: Original email dict (used for source tracking)

        Returns:
            Google Calendar event ID, or None on failure
        """
        try:
            event_time = self._build_event_time(appointment)
            if not event_time:
                logger.warning("Could not build event time, skipping")
                return None

            # Source email link for event description
            rfc822_id = email.get('rfc822_id', '')
            import urllib.parse
            gmail_url = (
                f"https://mail.google.com/mail/#search/rfc822msgid:{urllib.parse.quote(rfc822_id)}"
                if rfc822_id
                else f"https://mail.google.com/mail/#all/{email.get('id', '')}"
            )

            description_parts = []
            if appointment.get('description'):
                description_parts.append(appointment['description'])
            if appointment.get('meeting_link'):
                description_parts.append(f"Meeting link: {appointment['meeting_link']}")
            description_parts.append(f"Source email: {gmail_url}")

            event_body = {
                'summary': appointment.get('title', 'Appointment'),
                'description': '\n\n'.join(description_parts),
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': m}
                        for m in REMINDER_MINUTES
                    ],
                },
                # Store source email ID to detect duplicates
                'extendedProperties': {
                    'private': {
                        'source_email_id': email.get('id', ''),
                        'source_rfc822_id': email.get('rfc822_id', ''),
                    }
                },
            }

            # Location
            if appointment.get('location'):
                event_body['location'] = appointment['location']
            elif appointment.get('meeting_link'):
                event_body['location'] = appointment['meeting_link']

            # Start/end times
            event_body['start'] = event_time['start']
            event_body['end'] = event_time['end']

            result = self.service.events().insert(
                calendarId='primary',
                body=event_body,
            ).execute()

            event_id = result.get('id')
            logger.info(f"Calendar event created: {event_id} — {appointment.get('title')}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return None

    def event_exists_for_email(self, email_id: str) -> bool:
        """Check if a calendar event already exists for this email (prevents duplicates)."""
        try:
            events = self.service.events().list(
                calendarId='primary',
                privateExtendedProperty=f'source_email_id={email_id}',
                maxResults=1,
            ).execute()
            return len(events.get('items', [])) > 0
        except Exception as e:
            logger.error(f"Error checking for existing event: {e}")
            return False

    def _build_event_time(self, appointment: Dict) -> Optional[Dict]:
        """
        Build the start/end time dict for the Calendar API.

        Returns dict with 'start' and 'end' keys, or None if date is missing.
        """
        date_iso = appointment.get('date_iso', '')
        time_iso = appointment.get('time_iso', '')
        tz = appointment.get('timezone') or 'America/New_York'
        duration = appointment.get('duration_minutes') or 60

        if not date_iso:
            return None

        if time_iso:
            # Full datetime event
            start_str = f"{date_iso}T{time_iso}:00"
            start = {'dateTime': start_str, 'timeZone': tz}

            # Calculate end time
            try:
                from datetime import timedelta
                start_dt = datetime.fromisoformat(start_str)
                end_dt = start_dt + timedelta(minutes=duration)
                end_str = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                end = {'dateTime': end_str, 'timeZone': tz}
            except Exception:
                end = {'dateTime': start_str, 'timeZone': tz}
        else:
            # All-day event
            start = {'date': date_iso}
            end = {'date': date_iso}

        return {'start': start, 'end': end}
