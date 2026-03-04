"""Gmail Sync Service - Records emails sent/received directly in Gmail.

Periodically scans Gmail for emails exchanged with known contacts that were
sent outside of Veloro (directly via Gmail), and records them as EmailLog
entries so the contact's email history is complete.
"""

import logging
import threading
import time
import base64
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


class GmailSyncService:
    _thread = None

    @classmethod
    def sync_gmail_emails(cls):
        """Scan Gmail for emails to/from known contacts and record them."""
        from app import db
        from app.models import EmailLog, OAuthToken, Settings
        from app.models.contact import Contact
        from app.models.workspace import Workspace
        from app.services.gmail_service import GmailService

        accounts = OAuthToken.get_all_gmail_accounts()
        if not accounts:
            return {'synced_sent': 0, 'synced_received': 0, 'accounts_checked': 0}

        # Determine sync window - look back from last sync or default 7 days
        last_sync_str = Settings.get('gmail_sync_last_run')
        if last_sync_str:
            try:
                last_sync = datetime.fromisoformat(last_sync_str)
                # Add a small overlap to avoid missing emails
                sync_after = last_sync - timedelta(hours=1)
            except (ValueError, TypeError):
                sync_after = datetime.utcnow() - timedelta(days=7)
        else:
            sync_after = datetime.utcnow() - timedelta(days=7)

        total_sent = 0
        total_received = 0

        for account in accounts:
            gmail = GmailService(account_id=account.id)
            if not gmail.connect():
                continue

            sender_email = gmail.get_account_email()
            if not sender_email:
                continue

            # Get all workspaces to check contacts across them
            workspaces = Workspace.query.all()

            for workspace in workspaces:
                # Get all contact emails for this workspace
                contacts = Contact.query.filter(
                    Contact.workspace_id == workspace.id,
                    Contact.email.isnot(None),
                ).all()

                if not contacts:
                    continue

                contact_emails = {c.email.strip().lower(): c for c in contacts if c.email}

                # Sync sent emails
                sent_count = cls._sync_sent_emails(
                    gmail, account, sender_email, contact_emails,
                    workspace.id, sync_after, db,
                )
                total_sent += sent_count

                # Sync received emails
                received_count = cls._sync_received_emails(
                    gmail, account, sender_email, contact_emails,
                    workspace.id, sync_after, db,
                )
                total_received += received_count

        # Update last sync timestamp
        Settings.set('gmail_sync_last_run', datetime.utcnow().isoformat())
        db.session.commit()

        return {
            'synced_sent': total_sent,
            'synced_received': total_received,
            'accounts_checked': len(accounts),
        }

    @classmethod
    def _sync_sent_emails(cls, gmail, account, sender_email, contact_emails,
                          workspace_id, sync_after, db):
        """Sync emails sent from Gmail to known contacts."""
        from app.models import EmailLog

        # Format date for Gmail query
        after_date = sync_after.strftime('%Y/%m/%d')
        query = f'in:sent after:{after_date}'

        synced = 0
        try:
            messages = cls._list_messages(gmail, query)
        except Exception as e:
            logger.warning(f"Failed to list sent messages: {e}")
            return 0

        for msg_meta in messages:
            msg_id = msg_meta.get('id')
            if not msg_id:
                continue

            # Skip if we already have this message
            existing = EmailLog.query.filter_by(gmail_message_id=msg_id).first()
            if existing:
                continue

            try:
                msg = gmail.service.users().messages().get(
                    userId='me', id=msg_id, format='metadata',
                    metadataHeaders=['To', 'Subject', 'Date', 'From', 'Cc'],
                ).execute()

                headers = {
                    h['name']: h['value']
                    for h in msg.get('payload', {}).get('headers', [])
                }

                # Extract recipient emails from To and Cc
                to_header = headers.get('To', '')
                cc_header = headers.get('Cc', '')
                all_recipients = cls._extract_emails(to_header + ',' + cc_header)

                # Check if any recipient is a known contact
                matched_contact_email = None
                for recipient_email in all_recipients:
                    if recipient_email.lower() in contact_emails:
                        matched_contact_email = recipient_email.lower()
                        break

                if not matched_contact_email:
                    continue

                # Parse date
                sent_at = cls._parse_date(headers.get('Date', ''))
                subject = headers.get('Subject', '')
                thread_id = msg.get('threadId')

                # Create EmailLog entry
                log = EmailLog(
                    workspace_id=workspace_id,
                    gmail_message_id=msg_id,
                    gmail_thread_id=thread_id,
                    gmail_account_id=account.id,
                    recipient_email=matched_contact_email,
                    sender_email=sender_email,
                    subject=subject[:200] if subject else None,
                    status='sent',
                    source='gmail_sync',
                    direction='sent',
                    created_at=sent_at or datetime.utcnow(),
                )
                db.session.add(log)

                # Update contact stats
                contact = contact_emails.get(matched_contact_email)
                if contact:
                    cls._update_contact_stats(contact, sent_at, direction='sent')

                synced += 1

                # Commit in batches to avoid large transactions
                if synced % 50 == 0:
                    db.session.commit()

                # Rate limit
                time.sleep(0.05)

            except Exception as e:
                logger.warning(f"Failed to process sent message {msg_id}: {e}")
                continue

        if synced > 0:
            db.session.commit()

        return synced

    @classmethod
    def _sync_received_emails(cls, gmail, account, sender_email, contact_emails,
                              workspace_id, sync_after, db):
        """Sync emails received from known contacts."""
        from app.models import EmailLog

        after_date = sync_after.strftime('%Y/%m/%d')
        query = f'in:inbox after:{after_date}'

        synced = 0
        try:
            messages = cls._list_messages(gmail, query)
        except Exception as e:
            logger.warning(f"Failed to list received messages: {e}")
            return 0

        for msg_meta in messages:
            msg_id = msg_meta.get('id')
            if not msg_id:
                continue

            # Skip if we already have this message
            existing = EmailLog.query.filter_by(gmail_message_id=msg_id).first()
            if existing:
                continue

            try:
                msg = gmail.service.users().messages().get(
                    userId='me', id=msg_id, format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date', 'To'],
                ).execute()

                headers = {
                    h['name']: h['value']
                    for h in msg.get('payload', {}).get('headers', [])
                }

                from_header = headers.get('From', '')
                from_emails = cls._extract_emails(from_header)

                # Check if the sender is a known contact
                matched_contact_email = None
                for from_email in from_emails:
                    if from_email.lower() in contact_emails:
                        matched_contact_email = from_email.lower()
                        break

                if not matched_contact_email:
                    continue

                # Parse date
                received_at = cls._parse_date(headers.get('Date', ''))
                subject = headers.get('Subject', '')
                thread_id = msg.get('threadId')

                log = EmailLog(
                    workspace_id=workspace_id,
                    gmail_message_id=msg_id,
                    gmail_thread_id=thread_id,
                    gmail_account_id=account.id,
                    recipient_email=sender_email,
                    sender_email=matched_contact_email,
                    subject=subject[:200] if subject else None,
                    status='sent',
                    source='gmail_sync',
                    direction='received',
                    created_at=received_at or datetime.utcnow(),
                )
                db.session.add(log)

                # Update contact stats for received email
                contact = contact_emails.get(matched_contact_email)
                if contact:
                    cls._update_contact_stats(contact, received_at, direction='received')

                synced += 1

                if synced % 50 == 0:
                    db.session.commit()

                time.sleep(0.05)

            except Exception as e:
                logger.warning(f"Failed to process received message {msg_id}: {e}")
                continue

        if synced > 0:
            db.session.commit()

        return synced

    @classmethod
    def _list_messages(cls, gmail, query, max_results=500):
        """List Gmail messages matching query, handling pagination."""
        messages = []
        page_token = None

        while True:
            kwargs = {
                'userId': 'me',
                'q': query,
                'maxResults': min(100, max_results - len(messages)),
            }
            if page_token:
                kwargs['pageToken'] = page_token

            result = gmail.service.users().messages().list(**kwargs).execute()
            batch = result.get('messages', [])
            messages.extend(batch)

            page_token = result.get('nextPageToken')
            if not page_token or len(messages) >= max_results:
                break

        return messages

    @classmethod
    def _extract_emails(cls, header_value):
        """Extract email addresses from a header string like 'Name <email>, email2'."""
        if not header_value:
            return []
        return [m.lower().strip() for m in re.findall(r'[\w.+-]+@[\w.-]+\.\w+', header_value)]

    @classmethod
    def _parse_date(cls, date_str):
        """Parse an email date header into a datetime object."""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            return None

    @classmethod
    def _update_contact_stats(cls, contact, email_date, direction='sent'):
        """Update contact stats based on a synced email."""
        if direction == 'sent':
            if email_date:
                if not contact.first_contacted_at or email_date < contact.first_contacted_at:
                    contact.first_contacted_at = email_date
                if not contact.last_contacted_at or email_date > contact.last_contacted_at:
                    contact.last_contacted_at = email_date
            contact.total_emails_sent = (contact.total_emails_sent or 0) + 1
            if contact.status == 'new':
                contact.status = 'contacted'
        elif direction == 'received':
            if email_date:
                if not contact.last_replied_at or email_date > contact.last_replied_at:
                    contact.last_replied_at = email_date
            if contact.status in ('new', 'contacted'):
                contact.status = 'replied'

    @classmethod
    def start_background_polling(cls, app, interval=600):
        """Start a daemon thread that syncs Gmail emails periodically."""
        if cls._thread is not None:
            return

        def poll_loop():
            # Wait a bit on startup to let other services initialize
            time.sleep(30)
            while True:
                with app.app_context():
                    try:
                        result = cls.sync_gmail_emails()
                        if result['synced_sent'] > 0 or result['synced_received'] > 0:
                            app.logger.info(
                                f"Gmail sync: {result['synced_sent']} sent, "
                                f"{result['synced_received']} received"
                            )
                    except Exception as e:
                        app.logger.error(f'Gmail sync error: {e}')
                time.sleep(interval)

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Gmail sync started (interval={interval}s)')
