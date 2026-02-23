"""
Website Signal Collector — detects website-based intent signals:
SSL expiry, downtime, content changes, outdated copyright.

Ported from trigger_monitor.py into the signal collector framework.
"""
import ssl
import socket
import hashlib
import re
import json
import logging
import ipaddress
from datetime import datetime
from urllib.parse import urlparse

from app.services.signals.base import SignalCollector
from app.services.signals.registry import register_collector

logger = logging.getLogger(__name__)


def _is_safe_url(url):
    """Validate that a URL is safe for external fetching (not internal/private)."""
    if not url:
        return False
    if not url.startswith('http'):
        url = f'https://{url}'
    parsed = urlparse(url)
    hostname = (parsed.netloc or parsed.path).split(':')[0].strip()
    if not hostname:
        return False
    # Block obvious internal hostnames
    if hostname in ('localhost', '0.0.0.0'):
        return False
    # Block private/loopback IPs
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False
    except ValueError:
        pass  # It's a domain name, that's fine
    return True


@register_collector('website')
class WebsiteSignalCollector(SignalCollector):
    """Monitors contact websites for changes that create outreach opportunities."""

    source_type = 'website'

    def collect(self, contact, workspace_id, config=None):
        if not contact.website or not _is_safe_url(contact.website):
            return []

        signals = []

        try:
            signals.extend(self._check_ssl(contact, workspace_id))
        except Exception as e:
            logger.debug(f'SSL check failed for {contact.website}: {e}')

        try:
            signals.extend(self._check_downtime(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Downtime check failed for {contact.website}: {e}')

        try:
            signals.extend(self._check_content_change(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Content change check failed for {contact.website}: {e}')

        try:
            signals.extend(self._check_copyright(contact, workspace_id))
        except Exception as e:
            logger.debug(f'Copyright check failed for {contact.website}: {e}')

        return signals

    def _check_ssl(self, contact, workspace_id):
        from app.models.signal import Signal

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        parsed = urlparse(url)
        hostname = (parsed.netloc or parsed.path).split(':')[0]

        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after = ssl.cert_time_to_seconds(cert['notAfter'])
                    expiry_date = datetime.utcfromtimestamp(not_after)
                    days_until = (expiry_date - datetime.utcnow()).days

                    if days_until <= 30:
                        existing = Signal.query.filter_by(
                            contact_id=contact.id,
                            source_type='website',
                            signal_type='ssl_expiry',
                            dismissed=False,
                            actioned=False,
                        ).first()
                        if not existing:
                            severity = 'critical' if days_until <= 7 else 'important'
                            return [Signal(
                                workspace_id=workspace_id,
                                contact_id=contact.id,
                                source_type='website',
                                signal_type='ssl_expiry',
                                title=f'SSL certificate expires in {days_until} days',
                                summary=f'{hostname} SSL cert expires {expiry_date.strftime("%Y-%m-%d")}',
                                raw_data=json.dumps({
                                    'expiry_date': expiry_date.isoformat(),
                                    'days_until': days_until,
                                }),
                                intent_score=self.score_intent({'type': 'ssl_expiry', 'days_until': days_until}),
                                intent_category='pain_point',
                                severity=severity,
                            )]
        except Exception:
            pass

        return []

    def _check_downtime(self, contact, workspace_id):
        import requests as http_requests
        from app.models.signal import Signal

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = http_requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code >= 500:
                existing = Signal.query.filter_by(
                    contact_id=contact.id,
                    source_type='website',
                    signal_type='downtime',
                    dismissed=False,
                    actioned=False,
                ).first()
                if not existing:
                    return [Signal(
                        workspace_id=workspace_id,
                        contact_id=contact.id,
                        source_type='website',
                        signal_type='downtime',
                        title=f'Website returning {resp.status_code} error',
                        summary=f'{url} is down (HTTP {resp.status_code})',
                        raw_data=json.dumps({
                            'status_code': resp.status_code,
                            'checked_at': datetime.utcnow().isoformat(),
                        }),
                        intent_score=self.score_intent({'type': 'downtime'}),
                        intent_category='pain_point',
                        severity='critical',
                    )]
        except http_requests.exceptions.ConnectionError:
            existing = Signal.query.filter_by(
                contact_id=contact.id,
                source_type='website',
                signal_type='downtime',
                dismissed=False,
                actioned=False,
            ).first()
            if not existing:
                return [Signal(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    source_type='website',
                    signal_type='downtime',
                    title='Website unreachable',
                    summary=f'{url} connection failed',
                    raw_data=json.dumps({
                        'error': 'Connection failed',
                        'checked_at': datetime.utcnow().isoformat(),
                    }),
                    intent_score=self.score_intent({'type': 'downtime'}),
                    intent_category='pain_point',
                    severity='critical',
                )]
        except Exception:
            pass

        return []

    def _check_content_change(self, contact, workspace_id):
        import requests as http_requests
        from app.models.signal import Signal

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = http_requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code != 200:
                return []

            text = re.sub(r'\s+', ' ', resp.text).strip()
            current_hash = hashlib.md5(text.encode()).hexdigest()

            previous = Signal.query.filter_by(
                contact_id=contact.id,
                source_type='website',
                signal_type='content_change',
            ).order_by(Signal.created_at.desc()).first()

            if previous:
                prev_data = previous.get_raw_data()
                prev_hash = prev_data.get('hash') if isinstance(prev_data, dict) else None

                if prev_hash and prev_hash != current_hash:
                    existing = Signal.query.filter_by(
                        contact_id=contact.id,
                        source_type='website',
                        signal_type='content_change',
                        dismissed=False,
                        actioned=False,
                    ).first()
                    if not existing or existing.id == previous.id:
                        return [Signal(
                            workspace_id=workspace_id,
                            contact_id=contact.id,
                            source_type='website',
                            signal_type='content_change',
                            title='Website content changed',
                            summary=f'{url} homepage content has been modified',
                            raw_data=json.dumps({
                                'hash': current_hash,
                                'previous_hash': prev_hash,
                                'detected_at': datetime.utcnow().isoformat(),
                            }),
                            intent_score=self.score_intent({'type': 'content_change'}),
                            intent_category='growth',
                            severity='info',
                        )]
            else:
                # First time — store baseline (not actionable)
                from app import db
                baseline = Signal(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    source_type='website',
                    signal_type='content_change',
                    title='Content baseline captured',
                    raw_data=json.dumps({'hash': current_hash}),
                    intent_score=0.0,
                    severity='info',
                    dismissed=True,
                )
                db.session.add(baseline)
                db.session.commit()

        except Exception:
            pass

        return []

    def _check_copyright(self, contact, workspace_id):
        import requests as http_requests
        from app.models.signal import Signal

        url = contact.website
        if not url.startswith('http'):
            url = f'https://{url}'

        try:
            resp = http_requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code != 200:
                return []

            current_year = datetime.utcnow().year
            copyright_matches = re.findall(
                r'(?:©|&copy;|copyright)\s*(\d{4})',
                resp.text.lower()
            )

            if copyright_matches:
                latest_year = max(int(y) for y in copyright_matches)
                if latest_year < current_year - 1:
                    existing = Signal.query.filter_by(
                        contact_id=contact.id,
                        source_type='website',
                        signal_type='copyright_outdated',
                        dismissed=False,
                        actioned=False,
                    ).first()
                    if not existing:
                        severity = 'important' if latest_year < current_year - 2 else 'info'
                        return [Signal(
                            workspace_id=workspace_id,
                            contact_id=contact.id,
                            source_type='website',
                            signal_type='copyright_outdated',
                            title=f'Copyright year outdated ({latest_year})',
                            summary=f'{url} shows copyright {latest_year}, current year is {current_year}',
                            raw_data=json.dumps({
                                'copyright_year': latest_year,
                                'current_year': current_year,
                            }),
                            intent_score=self.score_intent({'type': 'copyright_outdated', 'years_old': current_year - latest_year}),
                            intent_category='pain_point',
                            severity=severity,
                        )]
        except Exception:
            pass

        return []

    def score_intent(self, signal_data):
        signal_type = signal_data.get('type', '')
        if signal_type == 'ssl_expiry':
            days = signal_data.get('days_until', 30)
            if days <= 7:
                return 0.9
            return 0.7
        elif signal_type == 'downtime':
            return 0.85
        elif signal_type == 'copyright_outdated':
            years_old = signal_data.get('years_old', 1)
            return min(0.8, 0.4 + years_old * 0.1)
        elif signal_type == 'content_change':
            return 0.3
        return 0.5
