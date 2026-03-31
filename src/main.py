#!/usr/bin/env python3
"""
Gmail Reminders — Main Entry Point

Monitors Gmail for appointment/scheduling emails and creates
Google Calendar events with multi-point reminders.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from gmail_client import GmailClient
from appointment_classifier import AppointmentClassifier
from appointment_extractor import AppointmentExtractor
from calendar_client import CalendarClient
from state_manager import EmailStateManager
from utils import load_config, setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Gmail for appointments and add calendar reminders"
    )
    parser.add_argument('--config', default='config/settings.yaml')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument(
        '--run',
        action='store_true',
        help='Check Gmail for new appointment emails and create calendar events'
    )
    parser.add_argument(
        '--reset-state',
        action='store_true',
        help='Clear processed email state'
    )

    args = parser.parse_args()
    load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level)

    if args.reset_state:
        state = EmailStateManager()
        state.state = {'processed_ids': [], 'last_run': None}
        state._save_state()
        logger.info("State cleared")
        return

    if not args.run:
        parser.print_help()
        return

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error(f"Config not found: {args.config}")
        sys.exit(1)

    try:
        gmail_client = GmailClient()
        classifier = AppointmentClassifier(config)
        extractor = AppointmentExtractor()
        calendar_client = CalendarClient(gmail_client.credentials)
        state_manager = EmailStateManager()
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        sys.exit(1)

    logger.info(f"State: {state_manager.get_stats()}")

    emails = gmail_client.get_recent_emails(
        max_results=config['gmail']['max_results'],
        labels=config['gmail']['labels_to_check'],
        days_back=config['gmail'].get('days_back', 1),
    )
    logger.info(f"Fetched {len(emails)} emails")

    created = 0
    skipped = 0

    for email in emails:
        email_id = email['id']

        # Skip already processed
        if state_manager.is_processed(email_id):
            skipped += 1
            continue

        # Skip if not appointment-related
        if not classifier.classify(email):
            continue

        logger.info(f"Appointment email detected: {email['subject'][:80]}")

        # Skip if calendar event already exists (extra safety net)
        if calendar_client.event_exists_for_email(email_id):
            logger.info(f"Calendar event already exists for {email_id}, skipping")
            state_manager.mark_processed(email_id)
            continue

        # Extract appointment details
        appointment = extractor.extract(email)
        if not appointment:
            logger.info(f"Could not extract date/time from: {email['subject'][:80]}")
            state_manager.mark_processed(email_id)
            continue

        logger.info(
            f"Extracted: {appointment.get('title')} on "
            f"{appointment.get('date_iso')} at {appointment.get('time_iso')} "
            f"({appointment.get('timezone')})"
        )

        # Create calendar event
        event_id = calendar_client.create_event(appointment, email)
        if event_id:
            created += 1
            logger.info(f"✅ Created calendar event: {appointment.get('title')}")
        else:
            logger.warning(f"Failed to create event for: {email['subject'][:80]}")

        state_manager.mark_processed(email_id)

    logger.info(f"Done — {created} events created, {skipped} emails already processed")


if __name__ == '__main__':
    main()
