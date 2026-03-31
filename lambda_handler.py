"""
AWS Lambda Handler — Gmail Reminders

Triggered on a schedule via EventBridge.
Checks Gmail for new appointment emails and creates Google Calendar events.
"""

import json
import logging
import sys
import os
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gmail_client import GmailClient
from appointment_classifier import AppointmentClassifier
from calendar_client import CalendarClient
from appointment_extractor import AppointmentExtractor
from state_manager import EmailStateManager
from utils import load_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def setup_credentials():
    config_dir = '/tmp/config'
    os.makedirs(config_dir, exist_ok=True)

    creds_b64 = os.environ.get('GMAIL_CREDENTIALS_B64', '')
    if creds_b64:
        with open(f'{config_dir}/credentials.json', 'w') as f:
            f.write(base64.b64decode(creds_b64).decode('utf-8'))

    token_b64 = os.environ.get('GMAIL_TOKEN_B64', '')
    if token_b64:
        with open(f'{config_dir}/token.pickle', 'wb') as f:
            f.write(base64.b64decode(token_b64))

    if os.path.exists('config/settings.yaml'):
        import shutil
        shutil.copy('config/settings.yaml', f'{config_dir}/settings.yaml')


def lambda_handler(event, context):
    try:
        logger.info("Gmail Reminders check starting...")
        setup_credentials()

        config_path = '/tmp/config/settings.yaml'
        if not os.path.exists(config_path):
            config_path = 'config/settings.yaml'

        config = load_config(config_path)

        gmail_client = GmailClient(credentials_path='/tmp/config/credentials.json')
        classifier = AppointmentClassifier(config)
        extractor = AppointmentExtractor()
        calendar_client = CalendarClient(gmail_client.credentials)
        state_manager = EmailStateManager()

        emails = gmail_client.get_recent_emails(
            max_results=config['gmail']['max_results'],
            labels=config['gmail']['labels_to_check'],
            days_back=config['gmail'].get('days_back', 1),
        )

        created = 0
        for email in emails:
            email_id = email['id']

            if state_manager.is_processed(email_id):
                continue
            if not classifier.classify(email):
                continue
            if calendar_client.event_exists_for_email(email_id):
                state_manager.mark_processed(email_id)
                continue

            appointment = extractor.extract(email)
            if not appointment:
                state_manager.mark_processed(email_id)
                continue

            event_id = calendar_client.create_event(appointment, email)
            if event_id:
                created += 1
                logger.info(f"Created event: {appointment.get('title')}")

            state_manager.mark_processed(email_id)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'emails_checked': len(emails),
                'events_created': created,
            }),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
        }
