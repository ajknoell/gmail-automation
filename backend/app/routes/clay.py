from flask import Blueprint, request, jsonify
from app import db
from app.models import Campaign, Recipient, Settings, OAuthToken
from datetime import datetime
import json
import hmac
import hashlib

clay_bp = Blueprint('clay', __name__)


def _verify_webhook_secret(req):
    """Verify Clay webhook secret if configured."""
    secret = Settings.get('clay_webhook_secret')
    if not secret:
        return True  # No secret configured, allow all

    signature = req.headers.get('X-Clay-Signature', '')
    if not signature:
        return False

    payload = req.get_data()
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@clay_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive enriched contacts from Clay.

    Accepts a JSON payload with contacts and optionally a campaign name/template.
    Creates a new campaign (or adds to existing) with the contacts as recipients.

    Expected payload:
    {
        "campaign_name": "Clay Import - Jan 2025",  // optional, auto-generated if missing
        "template_id": 1,                            // optional
        "campaign_id": 5,                            // optional - add to existing campaign
        "contacts": [
            {
                "email": "john@acme.com",
                "name": "John Smith",
                "company": "Acme Inc",
                "title": "CEO",
                "linkedin_url": "...",
                "website": "...",
                // ... any other enriched fields become custom_fields
            }
        ]
    }
    """
    if not _verify_webhook_secret(request):
        return jsonify({'error': 'Invalid webhook signature'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON payload'}), 400

    contacts = data.get('contacts', [])
    if not contacts:
        # Clay sometimes sends a single contact instead of an array
        if data.get('email'):
            contacts = [data]
        else:
            return jsonify({'error': 'No contacts provided'}), 400

    campaign_id = data.get('campaign_id')
    campaign = None

    if campaign_id:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': f'Campaign {campaign_id} not found'}), 404
        if campaign.status not in ['draft', 'paused']:
            return jsonify({'error': 'Cannot add to a running/completed campaign'}), 400
    else:
        # Create a new campaign
        campaign_name = data.get('campaign_name',
                                 f'Clay Import - {datetime.utcnow().strftime("%b %d, %Y %H:%M")}')
        template_id = data.get('template_id')

        # Get default Gmail account
        default_account = OAuthToken.get_default_gmail()
        gmail_account_id = default_account.id if default_account else None

        campaign = Campaign(
            name=campaign_name,
            template_id=template_id,
            gmail_account_id=gmail_account_id,
            use_ai_personalization=True,
            campaign_context=data.get('campaign_context', '')
        )
        db.session.add(campaign)
        db.session.flush()  # Get the campaign ID

    # Standard fields that map directly to recipient columns
    STANDARD_FIELDS = {'email', 'name', 'company'}
    imported = 0
    skipped = 0

    for contact in contacts:
        email = (contact.get('email') or '').strip()
        if not email or '@' not in email:
            skipped += 1
            continue

        # Check for duplicate in this campaign
        existing = Recipient.query.filter_by(
            campaign_id=campaign.id, email=email
        ).first()
        if existing:
            skipped += 1
            continue

        recipient = Recipient(
            campaign_id=campaign.id,
            email=email,
            name=contact.get('name', ''),
            company=contact.get('company', '')
        )

        # Everything else goes into custom_fields
        custom = {k: v for k, v in contact.items()
                  if k not in STANDARD_FIELDS and v}
        recipient.set_custom_fields(custom)
        db.session.add(recipient)
        imported += 1

    # Update total count
    campaign.total_recipients = Recipient.query.filter_by(
        campaign_id=campaign.id
    ).count()
    db.session.commit()

    return jsonify({
        'success': True,
        'campaign_id': campaign.id,
        'campaign_name': campaign.name,
        'imported': imported,
        'skipped': skipped,
        'total_recipients': campaign.total_recipients
    }), 201


@clay_bp.route('/settings', methods=['GET'])
def get_clay_settings():
    """Get Clay integration settings."""
    return jsonify({
        'clay_webhook_secret': Settings.get('clay_webhook_secret', ''),
        'clay_export_webhook_url': Settings.get('clay_export_webhook_url', ''),
        'clay_export_enabled': Settings.get('clay_export_enabled', 'false') == 'true',
    })


@clay_bp.route('/settings', methods=['POST'])
def save_clay_settings():
    """Save Clay integration settings."""
    data = request.get_json()

    if 'clay_webhook_secret' in data:
        Settings.set('clay_webhook_secret', data['clay_webhook_secret'])
    if 'clay_export_webhook_url' in data:
        Settings.set('clay_export_webhook_url', data['clay_export_webhook_url'])
    if 'clay_export_enabled' in data:
        Settings.set('clay_export_enabled',
                      'true' if data['clay_export_enabled'] else 'false')

    return jsonify({'success': True})


@clay_bp.route('/export/<int:campaign_id>', methods=['POST'])
def export_to_clay(campaign_id):
    """Manually trigger export of campaign tracking data to Clay."""
    from app.services.clay_export import ClayExportService

    if not ClayExportService.is_enabled():
        return jsonify({'error': 'Clay export not enabled. Configure webhook URL in settings.'}), 400

    result = ClayExportService.export_campaign_results(campaign_id)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@clay_bp.route('/webhook-url', methods=['GET'])
def get_webhook_url():
    """Return the inbound webhook URL for Clay to POST to."""
    from flask import request as req
    base = req.host_url.rstrip('/')
    return jsonify({
        'webhook_url': f'{base}/api/clay/webhook',
        'method': 'POST',
        'content_type': 'application/json',
        'example_payload': {
            'campaign_name': 'My Clay Campaign',
            'template_id': None,
            'contacts': [
                {
                    'email': 'john@acme.com',
                    'name': 'John Smith',
                    'company': 'Acme Inc',
                    'title': 'CEO',
                    'linkedin_url': 'https://linkedin.com/in/johnsmith',
                    'website': 'https://acme.com',
                    'industry': 'SaaS',
                    'funding_stage': 'Series A'
                }
            ]
        }
    })
