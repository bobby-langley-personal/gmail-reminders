"""
State Manager

Tracks which emails have already been processed to prevent duplicate calendar events.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

STATE_FILE = 'logs/reminder_state.json'
MAX_IDS = 2000


class EmailStateManager:
    """Tracks processed email IDs to avoid creating duplicate calendar events."""

    def __init__(self, state_file=None):
        self.state_file = state_file or (
            '/tmp/reminder_state.json' if os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
            else STATE_FILE
        )
        self.state = self._load_state()

    def _load_state(self) -> dict:
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
        return {'processed_ids': [], 'last_run': None}

    def _save_state(self):
        try:
            Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def is_processed(self, email_id: str) -> bool:
        return email_id in self.state['processed_ids']

    def mark_processed(self, email_id: str):
        ids = self.state['processed_ids']
        if email_id not in ids:
            ids.append(email_id)
            # Prune oldest entries
            if len(ids) > MAX_IDS:
                self.state['processed_ids'] = ids[-MAX_IDS:]
            self.state['last_run'] = datetime.now().isoformat()
            self._save_state()

    def get_new_emails(self, emails: List[Dict]) -> List[Dict]:
        """Filter to emails not yet processed."""
        new = [e for e in emails if not self.is_processed(e['email']['id'])]
        return new

    def get_stats(self) -> dict:
        return {
            'processed_count': len(self.state['processed_ids']),
            'last_run': self.state.get('last_run'),
        }
