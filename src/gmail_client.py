"""
Gmail API Client

Handles authentication and email retrieval from Gmail.
Copied from job-search-gmail-monitor with calendar scope added.
"""

import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

# Both gmail.readonly and calendar.events scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.events',
]


class GmailClient:
    """Wrapper for Gmail API operations."""

    def __init__(self, credentials_path='config/credentials.json'):
        self.credentials_path = credentials_path
        if credentials_path.startswith('/tmp'):
            self.token_path = '/tmp/config/token.pickle'
        else:
            self.token_path = 'config/token.pickle'
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail + Calendar APIs using OAuth."""
        creds = None

        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download OAuth credentials from Google Cloud Console"
                    )
                logger.info("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
            logger.info("Credentials saved")

        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail API client initialized")

        # Also expose credentials for Calendar client
        self.credentials = creds

    def get_recent_emails(self, max_results=50, labels=None, days_back=1):
        if labels is None:
            labels = ['INBOX']

        after_date = datetime.now() - timedelta(days=days_back)
        after_timestamp = int(after_date.timestamp())

        label_query = ' OR '.join([f'label:{label}' for label in labels])
        query = f'after:{after_timestamp} ({label_query})'

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
            ).execute()

            messages = results.get('messages', [])
            if not messages:
                return []

            emails = []
            for msg in messages:
                email_data = self._get_message_details(msg['id'])
                if email_data:
                    emails.append(email_data)

            return emails

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            raise

    def _get_message_details(self, msg_id):
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full',
            ).execute()

            headers = message['payload'].get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}

            body = self._extract_body(message['payload'])
            rfc822_id = header_dict.get('message-id', '').strip().strip('<>')

            return {
                'id': msg_id,
                'thread_id': message['threadId'],
                'rfc822_id': rfc822_id,
                'subject': header_dict.get('subject', ''),
                'from': header_dict.get('from', ''),
                'to': header_dict.get('to', ''),
                'date': header_dict.get('date', ''),
                'body': body,
                'snippet': message.get('snippet', ''),
                'labels': message.get('labelIds', []),
            }

        except Exception as e:
            logger.error(f"Error fetching message {msg_id}: {e}")
            return None

    def _extract_body(self, payload):
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        import base64
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
                        break
        elif 'body' in payload and 'data' in payload['body']:
            import base64
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8')
        return body
