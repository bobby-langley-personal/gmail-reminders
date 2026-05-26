"""
Appointment Classifier

Detects emails that contain a scheduled appointment, interview, meeting, or event.
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Subject/body phrases that strongly suggest a scheduled appointment
APPOINTMENT_PHRASES = [
    # Interviews
    'interview scheduled',
    'interview confirmed',
    'interview invitation',
    'you have been selected for an interview',
    'schedule your interview',
    'schedule an interview',
    'technical interview',
    'phone screen scheduled',
    'phone interview',
    'video interview',
    'on-site interview',
    'interview details',

    # General meetings
    'meeting scheduled',
    'meeting confirmed',
    'meeting invitation',
    'calendar invite',
    'calendar invitation',
    'you are invited to',
    'save the date',

    # Appointment confirmations
    'appointment confirmed',
    'appointment scheduled',
    'appointment reminder',
    'your appointment',
    'confirmed your booking',
    'scheduled',
    'booking has been confirmed'

    # Scheduling tools
    'calendly',
    'zoom meeting',
    'google meet',
    'microsoft teams meeting',
    'webex meeting',
    'has scheduled a meeting',
    'has invited you',
    'invited you to',
    'join zoom',
    'join the meeting',
    'scheduled'

    # ICS / calendar attachments (snippet text)
    'event.ics',
    'invite.ics',
    '.ics',
    'when:',
    'where:',
]

# Subject regex patterns
APPOINTMENT_PATTERNS = [
    r'interview\s+(scheduled|confirmed|invitation|request)',
    r'(scheduled|confirmed)\s+(interview|meeting|call|screen)',
    r'(phone|video|technical|onsite|on-site)\s+(screen|interview|call)',
    r'meeting\s+(invitation|request|scheduled)',
    r'invitation:\s+.+',
    r'accepted:\s+.+',
    r'(zoom|meet|teams|webex)\s+(meeting|call|invite)',
]


class AppointmentClassifier:
    """Classifies emails as containing a scheduled appointment."""

    def __init__(self, config: dict):
        self.config = config
        self.extra_phrases = config.get('appointment_phrases', [])
        self.exclusions = config.get('exclude', {})

    def classify(self, email: Dict) -> bool:
        """Return True if this email appears to contain a scheduled appointment."""
        subject = email.get('subject', '').lower()
        snippet = email.get('snippet', '').lower()
        body = email.get('body', '').lower()
        text = f"{subject} {snippet} {body}"

        # Check exclusions
        for excluded in self.exclusions.get('senders', []):
            if excluded.lower() in email.get('from', '').lower():
                return False
        for excluded in self.exclusions.get('subjects', []):
            if excluded.lower() in subject:
                return False

        # Phrase matching
        all_phrases = APPOINTMENT_PHRASES + self.extra_phrases
        for phrase in all_phrases:
            if phrase.lower() in text:
                logger.debug(f"Appointment phrase matched: '{phrase}'")
                return True

        # Regex pattern matching on subject
        for pattern in APPOINTMENT_PATTERNS:
            if re.search(pattern, subject, re.IGNORECASE):
                logger.debug(f"Appointment pattern matched: '{pattern}'")
                return True

        return False
