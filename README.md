# Gmail Reminders

Automatically detects appointment and scheduling emails in Gmail and creates Google Calendar events with multi-point reminders. Runs serverlessly on AWS Lambda every 15 minutes.

## How It Works

1. **Scans Gmail** for appointment-related emails (interviews, meetings, bookings, Calendly invites, Zoom links, etc.)
2. **Extracts event details** using Claude Haiku — title, date, time, timezone, duration, location, and meeting links
3. **Creates a Google Calendar event** with reminders at 15 minutes, 1 hour, 1 day, 1 week, and 2 weeks before
4. **Tracks processed emails** to prevent duplicate calendar events

## Architecture

```
EventBridge (every 15 min)
        │
        ▼
  AWS Lambda
        │
        ├── Gmail API ──── scan inbox for appointment emails
        ├── Claude Haiku ── extract structured event details
        └── Google Calendar API ── create event with reminders
```

## Tech Stack

- **Python 3.12** — Lambda runtime
- **AWS Lambda + EventBridge** — serverless scheduling
- **Gmail API** — email scanning (read-only)
- **Google Calendar API** — event creation
- **Claude Haiku** — AI-powered date/time and detail extraction
- **Google OAuth 2.0** — authentication

## Project Structure

```
gmail-reminders/
├── lambda_handler.py          # AWS Lambda entry point
├── src/
│   ├── gmail_client.py        # Gmail API — fetch recent emails
│   ├── appointment_classifier.py  # Keyword/regex detection
│   ├── appointment_extractor.py   # Claude Haiku extraction
│   ├── calendar_client.py     # Google Calendar event creation
│   ├── state_manager.py       # Tracks processed email IDs
│   └── utils.py               # Config loading, logging
├── config/
│   └── settings.yaml          # Gmail labels, exclusions, phrases
├── template.yaml              # AWS SAM template
└── requirements.txt
```

## Reminder Schedule

Each created calendar event gets popup notifications at:

| Reminder | When |
|----------|------|
| 15 minutes before | Final heads-up |
| 1 hour before | Prep time |
| 1 day before | Day-before notice |
| 1 week before | Week-out planning |
| 2 weeks before | Early awareness |

## Setup

### Prerequisites

- AWS account with IAM user credentials
- Google Cloud project with Gmail API and Google Calendar API enabled
- Anthropic API key
- OAuth credentials (`credentials.json`) and authorized token (`token.pickle`)

### Environment Variables (Lambda)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Haiku |
| `GMAIL_CREDENTIALS_B64` | Base64-encoded `credentials.json` |
| `GMAIL_TOKEN_B64` | Base64-encoded `token.pickle` |

### Deployment

```bash
# Encode credentials
CREDS=$(base64 -i config/credentials.json | tr -d '\n')
TOKEN=$(base64 -i config/token.pickle | tr -d '\n')

# Build and deploy via SAM
sam build
sam deploy --guided
```

Or deploy manually with the AWS CLI:

```bash
pip install -r requirements.txt -t .aws-build/ \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary :all:

cp -r src/* .aws-build/ && cp lambda_handler.py .aws-build/
cd .aws-build && zip -r ../gmail-reminders.zip . -x "*.pyc"

aws lambda update-function-code \
  --function-name gmail-reminders \
  --zip-file fileb://../gmail-reminders.zip
```

### Configuration (`config/settings.yaml`)

```yaml
gmail:
  max_results: 50
  labels_to_check:
    - INBOX
    - IMPORTANT
  days_back: 1

# Add custom phrases to detect beyond the defaults
appointment_phrases: []

# Skip emails from certain senders or with certain subjects
exclude:
  senders: []
  subjects:
    - "cancelled:"
    - "canceled:"
    - "declined:"
```

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY

cd src
python main.py --run           # scan Gmail and create events
python main.py --run --verbose # with debug logging
python main.py --reset-state   # clear processed email history
```

## Duplicate Prevention

Events are deduplicated at two levels:
1. **State file** — processed email IDs are cached to skip re-scanning
2. **Google Calendar query** — before creating an event, the Calendar API is queried for existing events tagged with the source email ID (stored as a private extended property)
