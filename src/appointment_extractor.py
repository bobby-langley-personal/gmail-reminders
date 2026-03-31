"""
Appointment Extractor

Uses Claude Haiku to extract structured event details from appointment emails.
Returns: title, date, time, timezone, duration, location, meeting_link, description.
"""

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AppointmentExtractor:
    """Extracts event details from appointment emails using Haiku."""

    def __init__(self):
        self.client = None
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
                logger.info("Appointment extractor initialized (Haiku)")
            except ImportError:
                logger.warning("anthropic package not installed")
        else:
            logger.warning("ANTHROPIC_API_KEY not set — extractor disabled")

    def extract(self, email: Dict) -> Optional[Dict]:
        """
        Extract appointment details from an email.

        Returns a dict with:
            title, date_iso, time_iso, timezone, duration_minutes,
            location, meeting_link, description, confidence

        Returns None if extraction fails or no clear date/time found.
        """
        if not self.client:
            return None

        try:
            prompt = f"""Extract appointment/meeting details from this email. Reply with JSON only, no markdown.

Subject: {email.get('subject', '')}
From: {email.get('from', '')}
Date received: {email.get('date', '')}
Snippet: {email.get('snippet', '')}
Body (first 1000 chars): {email.get('body', '')[:1000]}

Return exactly:
{{
  "title": "short event title (e.g. 'Technical Interview - Acme Corp')",
  "date_iso": "YYYY-MM-DD or empty string if not found",
  "time_iso": "HH:MM in 24h format or empty string if not found",
  "timezone": "timezone name like 'America/New_York' or 'EST' or empty string",
  "duration_minutes": number or null,
  "location": "physical address or empty string",
  "meeting_link": "zoom/meet/teams URL or empty string",
  "description": "brief description of the event",
  "confidence": 0.0 to 1.0
}}

If no specific date/time is mentioned, still return the object but with empty date_iso and time_iso.
Use the email received date as context for relative dates like 'tomorrow' or 'next Tuesday'."""

            message = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('\n', 1)[1]
                response_text = response_text.rsplit('\n', 1)[0]

            result = json.loads(response_text)

            # Require at least a date to be useful
            if not result.get('date_iso'):
                logger.debug("No date found in email, skipping calendar creation")
                return None

            return result

        except Exception as e:
            logger.error(f"Appointment extraction error: {e}")
            return None
