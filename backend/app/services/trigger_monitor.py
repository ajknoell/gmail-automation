"""
Trigger Monitor — watches contact websites for changes that create
outreach opportunities: SSL expiry, content changes, review shifts,
downtime, and outdated copyright.
"""
import ssl
import socket
import hashlib
import threading
import time
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TriggerMonitor:
    """Monitors contact websites for changes that create outreach opportunities."""
    _thread = None

    @classmethod
    def check_contact(cls, contact, workspace_id):
        """Run all trigger checks against a single contact's website."""
        if not contact.website:
            return []

        triggers = []

        try:
            triggers.extend(cls._check_ssl(contact, workspace_id))
        except Exception as e:
            logger.debug(f'SSL check failed for {contact.website}: {e}')

        try:
            triggers.extend(cls._check_downtime(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Downtime check failed for {contact.website}: {e}')

        try:
            triggers.extend(cls._check_content_change(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Content change check failed for {contact.website}: {e}')

        try:
            triggers.extend(cls._check_copyright(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Copyright check failed for {contact.website}: {e}')

        return triggers

    @classmethod
    def _check_ssl(cls, contact, workspace_id):
        """Check if SSL certificate expires within 30 days."""
        from app.models.website_trigger import WebsiteTrigger
        from urllib.parse import urlparse

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        parsed = urlparse(url)
        hostname = parsed.netloc or parsed.path

        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after = ssl.cert_time_to_seconds(cert['notAfter'])
                    expiry_date = datetime.utcfromtimestamp(not_after)
                    days_until = (expiry_date - datetime.utcnow()).days

                    if days_until <= 30:
                        # Check if we already have this trigger
                        existing = WebsiteTrigger.query.filter_by(
                            contact_id=contact.id,
                            trigger_type='ssl_expiry',
                            dismissed=False,
                            actioned=False,
                        ).first()
                        if not existing:
                            return [WebsiteTrigger(
                                workspace_id=workspace_id,
                                contact_id=contact.id,
                                trigger_type='ssl_expiry',
                                current_value=json.dumps({
                                    'expiry_date': expiry_date.isoformat(),
                                    'days_until': days_until,
                                }),
                                severity='critical' if days_until <= 7 else 'important',
                            )]
        except Exception:
            pass  # SSL check failure is not a trigger

        return []

    @classmethod
    def _check_downtime(cls, contact, workspace_id):
        """Check if website is down."""
        import requests
        from app.models.website_trigger import WebsiteTrigger

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code >= 500:
                existing = WebsiteTrigger.query.filter_by(
                    contact_id=contact.id,
                    trigger_type='downtime',
                    dismissed=False,
                    actioned=False,
                ).first()
                if not existing:
                    return [WebsiteTrigger(
                        workspace_id=workspace_id,
                        contact_id=contact.id,
                        trigger_type='downtime',
                        current_value=json.dumps({
                            'status_code': resp.status_code,
                            'checked_at': datetime.utcnow().isoformat(),
                        }),
                        severity='critical',
                    )]
        except requests.exceptions.ConnectionError:
            existing = WebsiteTrigger.query.filter_by(
                contact_id=contact.id,
                trigger_type='downtime',
                dismissed=False,
                actioned=False,
            ).first()
            if not existing:
                return [WebsiteTrigger(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    trigger_type='downtime',
                    current_value=json.dumps({
                        'error': 'Connection failed',
                        'checked_at': datetime.utcnow().isoformat(),
                    }),
                    severity='critical',
                )]
        except Exception:
            pass

        return []

    @classmethod
    def _check_content_change(cls, contact, workspace_id):
        """Hash homepage content and compare against stored hash."""
        import requests
        from app.models.website_trigger import WebsiteTrigger

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code != 200:
                return []

            # Hash the content (strip whitespace variations)
            import re
            text = re.sub(r'\s+', ' ', resp.text).strip()
            current_hash = hashlib.md5(text.encode()).hexdigest()

            # Get previous hash from most recent content_change trigger
            previous = WebsiteTrigger.query.filter_by(
                contact_id=contact.id,
                trigger_type='content_change',
            ).order_by(WebsiteTrigger.created_at.desc()).first()

            if previous:
                prev_data = previous.get_current_value()
                prev_hash = prev_data.get('hash') if isinstance(prev_data, dict) else None

                if prev_hash and prev_hash != current_hash:
                    # Content changed — only report if not dismissed recently
                    existing = WebsiteTrigger.query.filter_by(
                        contact_id=contact.id,
                        trigger_type='content_change',
                        dismissed=False,
                        actioned=False,
                    ).first()
                    if not existing or existing.id == previous.id:
                        return [WebsiteTrigger(
                            workspace_id=workspace_id,
                            contact_id=contact.id,
                            trigger_type='content_change',
                            previous_value=json.dumps({'hash': prev_hash}),
                            current_value=json.dumps({
                                'hash': current_hash,
                                'detected_at': datetime.utcnow().isoformat(),
                            }),
                            severity='info',
                        )]
            else:
                # First time — store baseline hash (not a trigger)
                from app import db
                baseline = WebsiteTrigger(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    trigger_type='content_change',
                    current_value=json.dumps({'hash': current_hash}),
                    severity='info',
                    dismissed=True,  # Baseline, not actionable
                )
                db.session.add(baseline)

        except Exception:
            pass

        return []

    @classmethod
    def _check_copyright(cls, contact, workspace_id):
        """Check for outdated copyright year on website."""
        import requests
        import re
        from app.models.website_trigger import WebsiteTrigger

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code != 200:
                return []

            current_year = datetime.utcnow().year
            # Look for copyright patterns
            copyright_matches = re.findall(
                r'(?:©|&copy;|copyright)\s*(\d{4})',
                resp.text.lower()
            )

            if copyright_matches:
                latest_year = max(int(y) for y in copyright_matches)
                if latest_year < current_year - 1:
                    existing = WebsiteTrigger.query.filter_by(
                        contact_id=contact.id,
                        trigger_type='copyright_outdated',
                        dismissed=False,
                        actioned=False,
                    ).first()
                    if not existing:
                        return [WebsiteTrigger(
                            workspace_id=workspace_id,
                            contact_id=contact.id,
                            trigger_type='copyright_outdated',
                            current_value=json.dumps({
                                'copyright_year': latest_year,
                                'current_year': current_year,
                            }),
                            severity='important' if latest_year < current_year - 2 else 'info',
                        )]
        except Exception:
            pass

        return []

    @classmethod
    def check_all_due(cls):
        """Check all contacts with websites that are due for monitoring."""
        from app import db
        from app.models.contact import Contact
        from app.models.settings import WorkspaceSettings
        from app.models.workspace import Workspace

        workspaces = Workspace.query.all()
        total_triggers = 0

        for ws in workspaces:
            # Check if trigger monitoring is enabled for this workspace
            config_raw = WorkspaceSettings.get(ws.id, 'trigger_monitor_config')
            config = {}
            if config_raw:
                try:
                    config = json.loads(config_raw)
                except Exception:
                    pass

            if not config.get('enabled', True):
                continue

            # Get contacts with websites, limit to 50 per run for rate limiting
            contacts = (
                Contact.query
                .filter(
                    Contact.workspace_id == ws.id,
                    Contact.website.isnot(None),
                    Contact.website != '',
                    Contact.status.notin_(['lost']),
                )
                .limit(50)
                .all()
            )

            for contact in contacts:
                try:
                    new_triggers = cls.check_contact(contact, ws.id)
                    for trigger in new_triggers:
                        db.session.add(trigger)
                        total_triggers += 1
                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f'Trigger check failed for contact {contact.id}: {e}')

            db.session.commit()

        return total_triggers

    @classmethod
    def start_background_polling(cls, app, interval=86400):
        """Start a daemon thread for periodic trigger checking."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        count = cls.check_all_due()
                        if count > 0:
                            app.logger.info(f'Trigger monitor found {count} new triggers')
                    except Exception as e:
                        app.logger.error(f'Trigger monitor error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Trigger monitor started (interval={interval}s)')
