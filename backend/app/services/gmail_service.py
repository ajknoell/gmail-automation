from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import json
from typing import Optional
from app import db
from app.models import OAuthToken

class GmailService:
    def __init__(self):
        self.service = None

    def _get_credentials(self) -> Optional[Credentials]:
        """Get valid Gmail credentials from database."""
        token = OAuthToken.query.filter_by(provider='gmail').first()
        if not token:
            return None

        creds = Credentials(
            token=token.token,
            refresh_token=token.refresh_token,
            token_uri=token.token_uri,
            client_id=token.client_id,
            client_secret=token.client_secret,
            scopes=json.loads(token.scopes) if token.scopes else None
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.token = creds.token
            token.expiry = creds.expiry
            db.session.commit()

        return creds

    def connect(self) -> bool:
        """Connect to Gmail API."""
        creds = self._get_credentials()
        if not creds:
            return False

        self.service = build('gmail', 'v1', credentials=creds)
        return True

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> dict:
        """Send an email via Gmail API."""
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        if html:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body, 'html'))
        else:
            message = MIMEText(body)

        message['to'] = to
        message['subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            return {
                'success': True,
                'message_id': result.get('id')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_profile(self) -> dict:
        """Get the authenticated user's email profile."""
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return {
                'email': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal'),
                'threads_total': profile.get('threadsTotal')
            }
        except Exception as e:
            return {'error': str(e)}


# Singleton instance
gmail_service = GmailService()
