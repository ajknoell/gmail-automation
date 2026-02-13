from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
import json
import os
from typing import Optional
from app import db
from app.models import OAuthToken

class GmailService:
    def __init__(self, account_id: Optional[int] = None):
        """Initialize GmailService.

        Args:
            account_id: Optional account ID. If None, uses the default account.
        """
        self.service = None
        self.account_id = account_id
        self._token = None

    def _get_credentials(self) -> Optional[Credentials]:
        """Get valid Gmail credentials from database."""
        if self.account_id:
            token = OAuthToken.get_by_id(self.account_id)
        else:
            token = OAuthToken.get_default_gmail()

        if not token:
            return None

        self._token = token

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
        html: bool = False,
        tracking_id: str = None,
        base_url: str = None,
        attachments: list = None,
    ) -> dict:
        """Send an email via Gmail API.

        Args:
            tracking_id: If provided, converts to HTML and injects tracking pixel + link rewriting.
            base_url: Base URL for tracking endpoints (e.g. http://localhost:5001).
        """
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        link_map = None

        if tracking_id and base_url:
            from app.services.tracking_service import TrackingService
            # Convert plain text to HTML if needed
            if not html:
                body = TrackingService.plain_text_to_html(body)
                html = True
            # Rewrite links for click tracking
            body, link_map = TrackingService.rewrite_links(body, tracking_id, base_url)
            # Inject tracking pixel
            body = TrackingService.inject_tracking_pixel(body, tracking_id, base_url)

        if attachments:
            # Mixed container: text + attachments
            message = MIMEMultipart('mixed')
            if html:
                text_part = MIMEMultipart('alternative')
                text_part.attach(MIMEText(body, 'html'))
                message.attach(text_part)
            else:
                message.attach(MIMEText(body))
            for att in attachments:
                self._attach_file(message, att)
        elif html:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body, 'html'))
        else:
            message = MIMEText(body)

        message['to'] = to.strip().replace('\n', '').replace('\r', '')
        message['subject'] = subject.strip().replace('\n', '').replace('\r', '')

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            return {
                'success': True,
                'message_id': result.get('id'),
                'thread_id': result.get('threadId'),
                'link_map': link_map,
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

    def get_thread(self, thread_id: str) -> dict:
        """Get a thread and its messages (metadata only)."""
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        return self.service.users().threads().get(
            userId='me',
            id=thread_id,
            format='metadata',
            metadataHeaders=['From', 'Date'],
        ).execute()

    def get_thread_full(self, thread_id: str) -> dict:
        """Get a thread with full message bodies."""
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        return self.service.users().threads().get(
            userId='me',
            id=thread_id,
            format='full',
        ).execute()

    @staticmethod
    def extract_reply_body(message: dict) -> str:
        """Extract plain text body from a Gmail message payload.

        Walks the MIME parts tree to find text/plain content.
        Falls back to text/html with tag stripping if no plain text found.
        """
        payload = message.get('payload', {})

        def _get_body_from_parts(parts):
            """Recursively search MIME parts for text content."""
            plain_text = None
            html_text = None

            for part in parts:
                mime_type = part.get('mimeType', '')
                data = part.get('body', {}).get('data')

                if mime_type == 'text/plain' and data:
                    plain_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                elif mime_type == 'text/html' and data:
                    html_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                elif part.get('parts'):
                    # Recurse into nested parts
                    nested = _get_body_from_parts(part['parts'])
                    if nested:
                        return nested

            return plain_text or html_text

        # Single-part message
        if payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='replace')

        # Multi-part message
        parts = payload.get('parts', [])
        if parts:
            return _get_body_from_parts(parts) or ''

        return ''

    @staticmethod
    def strip_quoted_text(body: str) -> str:
        """Strip quoted reply text to get just the new reply content."""
        import re

        lines = body.split('\n')
        clean_lines = []

        for line in lines:
            # Stop at common reply markers
            stripped = line.strip()
            if re.match(r'^On .+wrote:$', stripped):
                break
            if stripped.startswith('>'):
                break
            if re.match(r'^-{3,}\s*Original Message\s*-{3,}', stripped, re.IGNORECASE):
                break
            if re.match(r'^From:', stripped) and len(clean_lines) > 0:
                break
            clean_lines.append(line)

        return '\n'.join(clean_lines).strip()

    def send_reply(
        self,
        thread_id: str,
        message_id: str,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
        attachments: list = None,
    ) -> dict:
        """Send a reply within an existing Gmail thread.

        Args:
            thread_id: The Gmail thread ID to reply in.
            message_id: The Gmail message ID to reply to (for In-Reply-To header).
            to: Recipient email address.
            subject: Email subject (Re: prefix added automatically if missing).
            body: Email body text.
            html: Whether body is HTML.
        """
        if not self.service:
            if not self.connect():
                raise Exception("Gmail not connected")

        # Ensure Re: prefix
        if not subject.lower().startswith('re:'):
            subject = f'Re: {subject}'

        if attachments:
            message = MIMEMultipart('mixed')
            if html:
                text_part = MIMEMultipart('alternative')
                text_part.attach(MIMEText(body, 'html'))
                message.attach(text_part)
            else:
                message.attach(MIMEText(body))
            for att in attachments:
                self._attach_file(message, att)
        elif html:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body, 'html'))
        else:
            message = MIMEText(body)

        message['to'] = to.strip().replace('\n', '').replace('\r', '')
        message['subject'] = subject.strip().replace('\n', '').replace('\r', '')
        message['In-Reply-To'] = message_id
        message['References'] = message_id

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw, 'threadId': thread_id}
            ).execute()
            return {
                'success': True,
                'message_id': result.get('id'),
                'thread_id': result.get('threadId'),
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def _attach_file(message, attachment):
        """
        Attach a file to a MIME message.

        attachment: dict with keys:
            - filepath: absolute path to the file on disk
            - filename: display name for the attachment
            - content_type: MIME type (e.g. 'application/pdf')
        """
        filepath = attachment.get('filepath')
        filename = attachment.get('filename', os.path.basename(filepath))
        content_type = attachment.get('content_type', 'application/octet-stream')

        maintype, subtype = content_type.split('/', 1) if '/' in content_type else ('application', 'octet-stream')

        with open(filepath, 'rb') as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(part)

    def get_account_email(self) -> Optional[str]:
        """Get the email address of the connected account."""
        if self._token:
            return self._token.email_address
        return None
