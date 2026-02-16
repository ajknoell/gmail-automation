import threading
import time
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime


class ReplyChecker:
    _thread = None

    @classmethod
    def check_replies(cls):
        """Check all sent emails for replies. Returns summary dict."""
        from app import db
        from app.models import EmailLog, OAuthToken
        from app.models.reply_message import ReplyMessage
        from app.services.gmail_service import GmailService

        # Only check emails from last 30 days that haven't been replied to or bounced
        cutoff = datetime.utcnow() - timedelta(days=30)
        logs = (
            EmailLog.query
            .filter(
                EmailLog.status.in_(['sent', 'bounced']),
                EmailLog.replied_at.is_(None),
                EmailLog.gmail_thread_id.isnot(None),
                EmailLog.created_at > cutoff,
            )
            .all()
        )
        # Filter to only those needing checking (no reply AND no bounce yet)
        logs = [l for l in logs if not l.replied_at and not l.bounced_at]

        if not logs:
            return {'checked': 0, 'replies_found': 0, 'bounces_found': 0}

        # Group by gmail_account_id
        by_account = {}
        for log in logs:
            acct_id = log.gmail_account_id
            if acct_id not in by_account:
                by_account[acct_id] = []
            by_account[acct_id].append(log)

        replies_found = 0
        bounces_found = 0
        checked = 0

        for account_id, account_logs in by_account.items():
            gmail = GmailService(account_id=account_id)
            if not gmail.connect():
                continue

            # Get sender email for this account
            sender_email = gmail.get_account_email()

            for log in account_logs:
                try:
                    thread = gmail.get_thread_full(log.gmail_thread_id)
                    messages = thread.get('messages', [])

                    if len(messages) > 1:
                        # Check if any message after the first is from someone else
                        for msg in messages[1:]:
                            headers = {
                                h['name']: h['value']
                                for h in msg.get('payload', {}).get('headers', [])
                            }
                            from_header = headers.get('From', '')

                            # Check for bounce/delivery failure first
                            if cls._is_bounce(from_header, headers, msg):
                                if not log.bounced_at:
                                    log.bounced_at = datetime.utcnow()
                                    log.bounce_reason = cls._extract_bounce_reason(msg)
                                    log.status = 'bounced'
                                    bounces_found += 1

                                    # Update contact status
                                    try:
                                        from app.models.contact import Contact
                                        contact = Contact.query.filter_by(
                                            email=log.recipient_email,
                                            workspace_id=log.workspace_id,
                                        ).first()
                                        if contact and contact.status in ('new', 'contacted'):
                                            contact.status = 'bounced'
                                    except Exception:
                                        pass
                                break

                            # If the reply is from someone other than the sender
                            if sender_email and sender_email not in from_header:
                                msg_id = msg.get('id', '')

                                # Skip if we already stored this reply
                                existing = ReplyMessage.query.filter_by(gmail_message_id=msg_id).first()
                                if existing:
                                    continue

                                log.replied_at = datetime.utcnow()
                                replies_found += 1

                                # Extract reply body
                                full_body = GmailService.extract_reply_body(msg)
                                reply_text = GmailService.strip_quoted_text(full_body)

                                # Parse sender name from From header
                                from_name, from_email = cls._parse_from_header(from_header)

                                # Parse received date
                                received_at = None
                                date_header = headers.get('Date', '')
                                if date_header:
                                    try:
                                        received_at = parsedate_to_datetime(date_header)
                                    except Exception:
                                        received_at = datetime.utcnow()

                                # Get snippet from Gmail API response
                                snippet = msg.get('snippet', '')

                                # Create ReplyMessage record
                                reply_msg = ReplyMessage(
                                    email_log_id=log.id,
                                    gmail_message_id=msg_id,
                                    from_email=from_email or log.recipient_email,
                                    from_name=from_name,
                                    body_text=reply_text or snippet,
                                    snippet=snippet,
                                    received_at=received_at or datetime.utcnow(),
                                )
                                db.session.add(reply_msg)

                                # Classify sentiment (non-blocking — skip if API key not set)
                                try:
                                    cls._classify_reply(reply_msg, log)
                                except Exception:
                                    pass  # Sentiment stays null, can classify later

                                # Update contact directory (workspace-aware)
                                try:
                                    from app.models.contact import Contact
                                    contact = Contact.query.filter_by(
                                        email=log.recipient_email,
                                        workspace_id=log.workspace_id,
                                    ).first()
                                    if contact:
                                        contact.last_replied_at = log.replied_at
                                        # Auto-advance status to 'replied' if still in early stages
                                        if contact.status in ('new', 'contacted'):
                                            contact.status = 'replied'
                                except Exception:
                                    pass

                                # Push reply event to Clay
                                try:
                                    from app.services.clay_export import ClayExportService
                                    ClayExportService.export_single_event('reply', log)
                                except Exception:
                                    pass

                                # Auto-detect broker website for listing monitor
                                try:
                                    cls._auto_detect_broker_site(
                                        reply_text=reply_text or snippet,
                                        from_email=from_email or log.recipient_email,
                                        workspace_id=log.workspace_id,
                                    )
                                except Exception:
                                    pass
                                break

                    checked += 1
                    # Small delay to respect rate limits
                    time.sleep(0.1)

                except Exception:
                    continue

        # --- Second pass: detect responses sent directly via Gmail ---
        auto_responded = cls._check_gmail_responses(db, ReplyMessage, GmailService)

        db.session.commit()
        return {
            'checked': checked,
            'replies_found': replies_found,
            'bounces_found': bounces_found,
            'auto_responded': auto_responded,
        }

    # Keywords in reply text that suggest "check our listings"
    LISTING_HINT_RE = re.compile(
        r'check\s+(?:our|the|my)\s+listing|'
        r'visit\s+(?:our|the|my)\s+(?:website|site|page)|'
        r'browse\s+(?:our|the|my)\s+listing|'
        r'see\s+(?:our|the|my)\s+(?:website|current|available)|'
        r'distribution\s+list|'
        r'newsletter|'
        r'(?:add|added)\s+you\s+to\s+(?:our|the)|'
        r'sign\s+(?:our|the)\s+NDA|'
        r'notified\s+when',
        re.IGNORECASE,
    )

    @classmethod
    def _auto_detect_broker_site(cls, reply_text, from_email, workspace_id):
        """
        If a reply mentions checking listings/website, auto-create a MonitoredSite
        linked to the contact, using the sender's email domain.
        """
        if not reply_text or not from_email or not workspace_id:
            return

        # Check if the reply hints at monitoring their site
        if not cls.LISTING_HINT_RE.search(reply_text):
            return

        from app import db
        from app.models.contact import Contact
        from app.models.monitored_site import MonitoredSite

        # Extract domain from email
        domain = from_email.split('@')[-1].strip().lower()
        if not domain or domain in ('gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'comcast.net', 'aol.com'):
            # Generic email domain — try to find URLs in the reply text
            url_match = re.findall(r'https?://[^\s<>"\']+', reply_text)
            if url_match:
                # Use the first non-social URL
                for u in url_match:
                    if not re.search(r'linkedin\.com|facebook\.com|twitter\.com|instagram\.com', u, re.IGNORECASE):
                        domain = re.sub(r'^https?://(www\.)?', '', u).split('/')[0]
                        break
            if not domain or '.' not in domain:
                return

        site_url = f'https://{domain}'

        # Check if we already monitor this domain
        existing = MonitoredSite.query.filter(
            MonitoredSite.workspace_id == workspace_id,
            MonitoredSite.url.contains(domain),
        ).first()
        if existing:
            return

        # Find the contact
        contact = Contact.query.filter_by(
            email=from_email,
            workspace_id=workspace_id,
        ).first()

        # Try to get a proper site name from the domain
        site_name = domain.replace('.com', '').replace('.net', '').replace('.org', '').replace('.', ' ').title()

        site = MonitoredSite(
            workspace_id=workspace_id,
            name=site_name,
            url=site_url,
            contact_id=contact.id if contact else None,
            scraper_type='generic',
            check_interval_hours=24,
            is_active=True,
        )
        db.session.add(site)
        # Don't commit here — the caller will commit

    @classmethod
    def _check_gmail_responses(cls, db, ReplyMessage, GmailService):
        """Detect replies that were responded to directly in Gmail."""
        from app.models import EmailLog

        # Find reply messages that haven't been marked as responded
        cutoff = datetime.utcnow() - timedelta(days=30)
        unresponded = (
            ReplyMessage.query
            .join(EmailLog, ReplyMessage.email_log_id == EmailLog.id)
            .filter(
                ReplyMessage.response_sent_at.is_(None),
                ReplyMessage.received_at > cutoff,
            )
            .all()
        )

        if not unresponded:
            return 0

        # Group by gmail account
        by_account = {}
        for reply in unresponded:
            email_log = EmailLog.query.get(reply.email_log_id)
            if not email_log or not email_log.gmail_thread_id:
                continue
            acct_id = email_log.gmail_account_id
            if acct_id not in by_account:
                by_account[acct_id] = []
            by_account[acct_id].append((reply, email_log))

        auto_responded = 0

        for account_id, items in by_account.items():
            gmail = GmailService(account_id=account_id)
            if not gmail.connect():
                continue

            sender_email = gmail.get_account_email()
            if not sender_email:
                continue

            for reply, email_log in items:
                try:
                    thread = gmail.get_thread_full(email_log.gmail_thread_id)
                    messages = thread.get('messages', [])

                    # Find the reply message in the thread, then check if
                    # there's a subsequent message FROM the sender (us)
                    found_reply = False
                    for msg in messages:
                        msg_id = msg.get('id', '')
                        headers = {
                            h['name']: h['value']
                            for h in msg.get('payload', {}).get('headers', [])
                        }
                        from_header = headers.get('From', '')

                        if msg_id == reply.gmail_message_id:
                            found_reply = True
                            continue

                        # After the reply, look for a message from us
                        if found_reply and sender_email in from_header:
                            reply.response_sent_at = datetime.utcnow()
                            auto_responded += 1
                            break

                    time.sleep(0.1)
                except Exception:
                    continue

        return auto_responded

    @classmethod
    def _parse_from_header(cls, from_header: str):
        """Parse a From header like 'John Smith <john@example.com>' into (name, email)."""
        match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', from_header)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        # Bare email address
        email_match = re.match(r'^([^\s@]+@[^\s@]+)', from_header)
        if email_match:
            return None, email_match.group(1).strip()
        return None, from_header.strip()

    # Patterns that indicate a bounce/delivery failure sender
    BOUNCE_SENDERS = re.compile(
        r'mailer-daemon|postmaster|mail-delivery|noreply.*bounce|'
        r'automailer|mail-noreply@google\.com',
        re.IGNORECASE,
    )

    # Subject patterns for bounces
    BOUNCE_SUBJECTS = re.compile(
        r'delivery.*(?:fail|status|notif)|undeliverable|returned mail|'
        r'mail delivery failed|message not delivered|address rejected|'
        r'could not be delivered|permanent failure',
        re.IGNORECASE,
    )

    @classmethod
    def _is_bounce(cls, from_header: str, headers: dict, msg: dict) -> bool:
        """Detect if a message is a bounce/delivery failure notification."""
        # Check sender
        if cls.BOUNCE_SENDERS.search(from_header):
            return True

        # Check subject
        subject = headers.get('Subject', '')
        if cls.BOUNCE_SUBJECTS.search(subject):
            return True

        # Check for DSN (Delivery Status Notification) content type
        content_type = headers.get('Content-Type', '')
        if 'delivery-status' in content_type.lower():
            return True

        # Check snippet for common bounce phrases
        snippet = (msg.get('snippet', '') or '').lower()
        bounce_phrases = [
            'address not found', 'user unknown', 'mailbox not found',
            'no such user', 'does not exist', 'address rejected',
            'delivery has failed', 'undeliverable', 'permanent failure',
            'message not delivered', '550 ', '551 ', '552 ', '553 ', '554 ',
        ]
        if any(phrase in snippet for phrase in bounce_phrases):
            return True

        return False

    @classmethod
    def _extract_bounce_reason(cls, msg: dict) -> str:
        """Extract a human-readable bounce reason from the message."""
        snippet = msg.get('snippet', '')
        if snippet:
            # Truncate to something reasonable
            return snippet[:300]
        return 'Delivery failed'

    @classmethod
    def _classify_reply(cls, reply_msg, email_log):
        """Run sentiment classification on a reply message."""
        from app.models import Settings
        from app.services.claude_service import ClaudeService

        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return

        claude = ClaudeService(api_key)
        result = claude.classify_sentiment(
            original_subject=email_log.subject or '',
            original_body=email_log.body or '',
            reply_text=reply_msg.body_text or reply_msg.snippet or '',
        )

        if result:
            reply_msg.sentiment = result.get('sentiment')
            reply_msg.sentiment_reason = result.get('reason')

    @classmethod
    def start_background_polling(cls, app, interval=300):
        """Start a daemon thread that polls for replies periodically."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        cls.check_replies()
                    except Exception as e:
                        app.logger.error(f'Reply check error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Reply checker started (interval={interval}s)')
