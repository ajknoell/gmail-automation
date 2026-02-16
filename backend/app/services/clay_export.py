"""Service to push tracking data back to Clay via outbound webhooks."""
import requests
import json
import logging
from typing import Optional
from app.models import Settings, Campaign, Recipient, EmailLog

logger = logging.getLogger(__name__)


class ClayExportService:
    """Pushes campaign tracking data to Clay's webhook endpoint."""

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if Clay export is configured and enabled."""
        enabled = Settings.get('clay_export_enabled', 'false') == 'true'
        url = Settings.get('clay_export_webhook_url', '')
        return enabled and bool(url)

    @classmethod
    def get_webhook_url(cls) -> Optional[str]:
        """Get the configured Clay export webhook URL."""
        return Settings.get('clay_export_webhook_url')

    @classmethod
    def export_campaign_results(cls, campaign_id: int) -> dict:
        """Export all tracking results for a campaign to Clay.

        Sends each recipient's tracking data as a separate webhook call,
        or batches them depending on Clay's expected format.
        """
        if not cls.is_enabled():
            return {'success': False, 'error': 'Clay export not enabled'}

        webhook_url = cls.get_webhook_url()
        if not webhook_url:
            return {'success': False, 'error': 'No webhook URL configured'}

        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}

        recipients = Recipient.query.filter_by(campaign_id=campaign_id).all()
        logs = EmailLog.query.filter_by(campaign_id=campaign_id).all()
        tracking_by_recipient = {l.recipient_id: l for l in logs}

        results = []
        for recipient in recipients:
            log = tracking_by_recipient.get(recipient.id)
            entry = {
                'email': recipient.email,
                'name': recipient.name,
                'company': recipient.company,
                'campaign_name': campaign.name,
                'status': recipient.status,
                'sent_at': recipient.sent_at.isoformat() if recipient.sent_at else None,
                'opened': bool(log and log.opened_at),
                'opened_at': log.opened_at.isoformat() if log and log.opened_at else None,
                'open_count': log.open_count if log else 0,
                'clicked': bool(log and log.clicked_at),
                'clicked_at': log.clicked_at.isoformat() if log and log.clicked_at else None,
                'click_count': log.click_count if log else 0,
                'replied': bool(log and log.replied_at),
                'replied_at': log.replied_at.isoformat() if log and log.replied_at else None,
            }
            results.append(entry)

        # Send batch to Clay webhook
        payload = {
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'exported_at': __import__('datetime').datetime.utcnow().isoformat(),
            'results': results
        }

        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            resp.raise_for_status()
            return {
                'success': True,
                'exported': len(results),
                'status_code': resp.status_code
            }
        except requests.RequestException as e:
            logger.error(f'Clay export failed for campaign {campaign_id}: {e}')
            return {
                'success': False,
                'error': str(e),
                'exported': 0
            }

    @classmethod
    def export_single_event(cls, event_type: str, email_log: 'EmailLog',
                            recipient: 'Recipient' = None) -> bool:
        """Export a single tracking event (open/click/reply) to Clay in real-time.

        Args:
            event_type: 'open', 'click', or 'reply'
            email_log: The EmailLog record with tracking data
            recipient: Optional Recipient for extra context
        """
        if not cls.is_enabled():
            return False

        webhook_url = cls.get_webhook_url()
        if not webhook_url:
            return False

        payload = {
            'event': event_type,
            'email': email_log.recipient_email or (recipient.email if recipient else ''),
            'campaign_id': email_log.campaign_id,
            'tracking_id': email_log.tracking_id,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
        }

        if recipient:
            payload['name'] = recipient.name
            payload['company'] = recipient.company

        if event_type == 'open':
            payload['open_count'] = email_log.open_count
        elif event_type == 'click':
            payload['click_count'] = email_log.click_count

        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            return resp.ok
        except requests.RequestException as e:
            logger.warning(f'Clay real-time export failed: {e}')
            return False
