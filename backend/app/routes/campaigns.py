from flask import Blueprint, request, jsonify, Response, current_app
from app import db
from app.models import Campaign, Recipient, Template, EmailLog, Settings
from app.services.csv_parser import parse_file, detect_field_mapping
from app.services.claude_service import ClaudeService, clean_company_name
from app.services.campaign_runner import CampaignRunner
import re
from datetime import datetime
import json
import csv
import io

campaigns_bp = Blueprint('campaigns', __name__)

@campaigns_bp.route('', methods=['GET'])
def list_campaigns():
    """List all campaigns."""
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in campaigns])

@campaigns_bp.route('/<int:id>', methods=['GET'])
def get_campaign(id):
    """Get a single campaign with stats."""
    campaign = Campaign.query.get_or_404(id)
    return jsonify(campaign.to_dict(include_template=True))

@campaigns_bp.route('', methods=['POST'])
def create_campaign():
    """Create a new campaign."""
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    campaign = Campaign(
        name=data['name'],
        template_id=data.get('template_id'),
        delay_seconds=data.get('delay_seconds', 30),
        use_ai_personalization=data.get('use_ai_personalization', True),
        ai_prompt=data.get('ai_prompt')
    )

    db.session.add(campaign)
    db.session.commit()

    return jsonify(campaign.to_dict()), 201

@campaigns_bp.route('/<int:id>', methods=['PUT'])
def update_campaign(id):
    """Update a campaign."""
    campaign = Campaign.query.get_or_404(id)
    data = request.get_json()

    if campaign.status not in ['draft', 'paused']:
        return jsonify({'error': 'Cannot update running campaign'}), 400

    if 'name' in data:
        campaign.name = data['name']
    if 'template_id' in data:
        campaign.template_id = data['template_id']
    if 'delay_seconds' in data:
        campaign.delay_seconds = data['delay_seconds']
    if 'use_ai_personalization' in data:
        campaign.use_ai_personalization = data['use_ai_personalization']
    if 'ai_prompt' in data:
        campaign.ai_prompt = data['ai_prompt']

    db.session.commit()
    return jsonify(campaign.to_dict())

@campaigns_bp.route('/<int:id>', methods=['DELETE'])
def delete_campaign(id):
    """Delete a campaign."""
    campaign = Campaign.query.get_or_404(id)

    if campaign.status == 'running':
        return jsonify({'error': 'Cannot delete running campaign'}), 400

    db.session.delete(campaign)
    db.session.commit()
    return jsonify({'success': True})

@campaigns_bp.route('/<int:id>/upload', methods=['POST'])
def upload_recipients(id):
    """Upload CSV/Excel file with recipients."""
    campaign = Campaign.query.get_or_404(id)

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    try:
        content = file.read()
        headers, rows = parse_file(content, file.filename)
        mapping = detect_field_mapping(headers)

        # Get field mapping from request or use auto-detected
        field_mapping = request.form.get('mapping')
        if field_mapping:
            mapping.update(json.loads(field_mapping))

        # Clear existing recipients
        Recipient.query.filter_by(campaign_id=id).delete()

        # Import recipients
        for row in rows:
            email = row.get(mapping.get('email', ''), '').strip()
            if not email or '@' not in email:
                continue

            recipient = Recipient(
                campaign_id=id,
                email=email,
                name=row.get(mapping.get('name', ''), ''),
                company=row.get(mapping.get('company', ''), '')
            )

            # Store all other fields as custom_fields
            custom = {k: v for k, v in row.items()
                     if k not in [mapping.get('email'), mapping.get('name'), mapping.get('company')]}
            recipient.set_custom_fields(custom)

            db.session.add(recipient)

        campaign.total_recipients = Recipient.query.filter_by(campaign_id=id).count()
        db.session.commit()

        return jsonify({
            'success': True,
            'headers': headers,
            'mapping': mapping,
            'total_recipients': campaign.total_recipients
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@campaigns_bp.route('/<int:id>/recipients', methods=['GET'])
def list_recipients(id):
    """List recipients for a campaign."""
    campaign = Campaign.query.get_or_404(id)
    recipients = Recipient.query.filter_by(campaign_id=id).all()
    return jsonify([r.to_dict() for r in recipients])

def _substitute_template_variables(text, recipient):
    """Replace {{variable}} placeholders with recipient data."""
    variables = {
        'name': recipient.name or '',
        'email': recipient.email or '',
        'company': clean_company_name(recipient.company or '') or '',
    }
    custom = recipient.get_custom_fields()
    if custom:
        variables.update(custom)

    def replace_var(match):
        key = match.group(1)
        return variables.get(key, match.group(0))

    return re.sub(r'\{\{(\w+)\}\}', replace_var, text)


@campaigns_bp.route('/<int:id>/generate-preview', methods=['POST'])
def generate_preview(id):
    """Generate personalized emails for preview (AI or simple substitution).

    Accepts optional JSON body:
        batch_size: Number of emails to generate (default 50, 0 for all)
    """
    campaign = Campaign.query.get_or_404(id)

    if not campaign.template:
        return jsonify({'error': 'No template selected'}), 400

    data = request.get_json(silent=True) or {}
    batch_size = data.get('batch_size', 50)

    # Load all pending recipients, then filter out already-personalized ones in Python
    # (avoids SQL NULL comparison issues across different DB engines)
    all_pending = Recipient.query.filter_by(campaign_id=id, status='pending').all()
    unpersonalized = [r for r in all_pending if not r.personalized_body]

    if batch_size > 0:
        recipients = unpersonalized[:batch_size]
    else:
        recipients = unpersonalized

    remaining = len(unpersonalized) - len(recipients) if batch_size > 0 else 0

    generated = 0
    failed = 0

    if campaign.use_ai_personalization:
        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return jsonify({'error': 'Anthropic API key not configured'}), 400

        claude = ClaudeService(api_key)

        for recipient in recipients:
            try:
                result = claude.personalize_email(
                    template_subject=campaign.template.subject,
                    template_body=campaign.template.body,
                    recipient={
                        'name': recipient.name,
                        'email': recipient.email,
                        'company': recipient.company,
                        'custom_fields': recipient.get_custom_fields()
                    },
                    custom_prompt=campaign.ai_prompt
                )
                recipient.personalized_subject = result.get('subject', campaign.template.subject)
                recipient.personalized_body = result.get('body', campaign.template.body)
                generated += 1
            except Exception as e:
                # Fall back to simple variable substitution on AI failure
                recipient.personalized_subject = _substitute_template_variables(
                    campaign.template.subject, recipient)
                recipient.personalized_body = _substitute_template_variables(
                    campaign.template.body, recipient)
                failed += 1
    else:
        # Simple {{variable}} substitution without AI
        for recipient in recipients:
            recipient.personalized_subject = _substitute_template_variables(
                campaign.template.subject, recipient)
            recipient.personalized_body = _substitute_template_variables(
                campaign.template.body, recipient)
            generated += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'generated': generated,
        'failed': failed,
        'remaining': remaining
    })

@campaigns_bp.route('/<int:id>/send-individual', methods=['POST'])
def send_individual(id):
    """Send email to a single recipient."""
    campaign = Campaign.query.get_or_404(id)

    data = request.get_json()
    recipient_id = data.get('recipient_id')
    if not recipient_id:
        return jsonify({'error': 'recipient_id is required'}), 400

    recipient = Recipient.query.filter_by(id=recipient_id, campaign_id=id).first()
    if not recipient:
        return jsonify({'error': 'Recipient not found'}), 404

    if recipient.status == 'sent':
        return jsonify({'error': 'Email already sent to this recipient'}), 400

    if not recipient.personalized_body:
        return jsonify({'error': 'No personalized content generated for this recipient'}), 400

    from app.services.gmail_service import GmailService
    gmail = GmailService()
    if not gmail.connect():
        return jsonify({'error': 'Gmail not connected'}), 400

    subject = recipient.personalized_subject or 'No subject'
    body = recipient.personalized_body

    result = gmail.send_email(to=recipient.email, subject=subject, body=body)

    if result.get('success'):
        recipient.status = 'sent'
        recipient.sent_at = datetime.utcnow()
        campaign.sent_count += 1

        log = EmailLog(
            recipient_id=recipient.id,
            campaign_id=id,
            gmail_message_id=result.get('message_id'),
            subject=subject,
            body=body,
            status='sent'
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({'success': True, 'status': 'sent'})
    else:
        error = result.get('error', 'Unknown error')
        recipient.status = 'failed'
        recipient.error_message = error
        campaign.failed_count += 1

        log = EmailLog(
            recipient_id=recipient.id,
            campaign_id=id,
            subject=subject,
            status='failed',
            error_details=error
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({'error': f'Failed to send: {error}'}), 500

@campaigns_bp.route('/<int:id>/approve', methods=['POST'])
def approve_recipients(id):
    """Approve recipients for sending."""
    data = request.get_json()
    recipient_ids = data.get('recipient_ids', [])

    if recipient_ids:
        Recipient.query.filter(Recipient.id.in_(recipient_ids)).update({'approved': True}, synchronize_session=False)
    else:
        # Approve all
        Recipient.query.filter_by(campaign_id=id, status='pending').update({'approved': True}, synchronize_session=False)

    db.session.commit()
    return jsonify({'success': True})

@campaigns_bp.route('/<int:id>/start', methods=['POST'])
def start_campaign(id):
    """Start sending campaign."""
    campaign = Campaign.query.get_or_404(id)

    if campaign.status == 'running':
        return jsonify({'error': 'Campaign already running'}), 400

    recipients = Recipient.query.filter_by(
        campaign_id=id,
        status='pending',
        approved=True
    ).all()

    if not recipients:
        return jsonify({'error': 'No approved recipients to send to'}), 400

    campaign.status = 'running'
    campaign.started_at = datetime.utcnow()
    db.session.commit()

    # Start campaign runner in background
    CampaignRunner.start(campaign.id, [r.id for r in recipients], campaign.delay_seconds)

    return jsonify({'success': True, 'status': 'running'})

@campaigns_bp.route('/<int:id>/pause', methods=['POST'])
def pause_campaign(id):
    """Pause a running campaign."""
    campaign = Campaign.query.get_or_404(id)

    if campaign.status != 'running':
        return jsonify({'error': 'Campaign is not running'}), 400

    CampaignRunner.pause(id)
    campaign.status = 'paused'
    db.session.commit()

    return jsonify({'success': True, 'status': 'paused'})

@campaigns_bp.route('/<int:id>/resume', methods=['POST'])
def resume_campaign(id):
    """Resume a paused campaign."""
    campaign = Campaign.query.get_or_404(id)

    if campaign.status != 'paused':
        return jsonify({'error': 'Campaign is not paused'}), 400

    CampaignRunner.resume(id)
    campaign.status = 'running'
    db.session.commit()

    return jsonify({'success': True, 'status': 'running'})

@campaigns_bp.route('/<int:id>/cancel', methods=['POST'])
def cancel_campaign(id):
    """Cancel a campaign."""
    campaign = Campaign.query.get_or_404(id)

    if campaign.status not in ['running', 'paused']:
        return jsonify({'error': 'Campaign is not active'}), 400

    CampaignRunner.cancel(id)
    campaign.status = 'cancelled'
    db.session.commit()

    return jsonify({'success': True, 'status': 'cancelled'})

@campaigns_bp.route('/<int:id>/progress')
def campaign_progress(id):
    """Stream campaign progress using SSE."""
    def generate():
        import time
        while True:
            campaign = Campaign.query.get(id)
            if not campaign:
                yield f"data: {json.dumps({'error': 'Campaign not found'})}\n\n"
                break

            state = CampaignRunner.get_state(id)
            data = {
                'sent': campaign.sent_count,
                'failed': campaign.failed_count,
                'total': campaign.total_recipients,
                'status': campaign.status,
                'is_running': state is not None
            }
            yield f"data: {json.dumps(data)}\n\n"

            if campaign.status in ['completed', 'cancelled']:
                break

            time.sleep(1)

    return Response(generate(), mimetype='text/event-stream')

@campaigns_bp.route('/<int:id>/export')
def export_campaign(id):
    """Export campaign results as CSV."""
    campaign = Campaign.query.get_or_404(id)
    recipients = Recipient.query.filter_by(campaign_id=id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Name', 'Company', 'Status', 'Sent At', 'Error'])

    for r in recipients:
        writer.writerow([
            r.email,
            r.name,
            r.company,
            r.status,
            r.sent_at.isoformat() if r.sent_at else '',
            r.error_message or ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=campaign_{id}_results.csv'}
    )
