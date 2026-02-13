from flask import Blueprint, request, jsonify, current_app, g
from app import db
from app.models import Settings, OAuthToken, EmailLog
from app.models.template import Template
from app.models.settings import WorkspaceSettings
from app.services.claude_service import ClaudeService
from app.services.gmail_service import GmailService
from app.services.tracking_service import TrackingService
import json

quick_send_bp = Blueprint('quick_send', __name__)


def _resolve_attachments(attachment_ids):
    """Resolve attachment IDs to file info dicts for GmailService."""
    if not attachment_ids:
        return []

    import os
    upload_dir = os.path.join(
        current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'uploads')),
        'attachments',
    )
    results = []
    for att in attachment_ids:
        # att can be a dict {id, filename, original_name, ...} or just an id string
        file_id = att.get('id') if isinstance(att, dict) else att
        filename = att.get('original_name', '') if isinstance(att, dict) else ''
        content_type = att.get('content_type', 'application/octet-stream') if isinstance(att, dict) else 'application/octet-stream'
        stored_name = att.get('filename', '') if isinstance(att, dict) else ''

        # Find the file on disk
        if stored_name and os.path.exists(os.path.join(upload_dir, stored_name)):
            results.append({
                'filepath': os.path.join(upload_dir, stored_name),
                'filename': filename or stored_name,
                'content_type': content_type,
            })
        else:
            # Search by ID prefix
            for fname in os.listdir(upload_dir):
                if fname.startswith(str(file_id) + '_'):
                    results.append({
                        'filepath': os.path.join(upload_dir, fname),
                        'filename': filename or fname.split('_', 1)[1] if '_' in fname else fname,
                        'content_type': content_type,
                    })
                    break
    return results

@quick_send_bp.route('/generate', methods=['POST'])
def generate_quick_email():
    """Generate a one-off personalized email.

    If template_id is provided, uses the template with personalize_email().
    Otherwise falls back to the freeform generate_quick_email().
    """
    data = request.get_json()
    recipient = data.get('recipient', {})
    context = data.get('context', '')
    template_id = data.get('template_id')

    if not recipient.get('email'):
        return jsonify({'error': 'Email address is required'}), 400

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    # Get writing style (workspace-scoped, fallback to global)
    writing_style_raw = WorkspaceSettings.get(g.workspace_id, 'writing_style')
    if not writing_style_raw:
        writing_style_raw = Settings.get('writing_style')
    writing_style = None
    if writing_style_raw:
        try:
            writing_style = json.loads(writing_style_raw) if isinstance(writing_style_raw, str) else writing_style_raw
        except Exception:
            pass

    # Load learned insights for this workspace
    learned_insights = None
    insights_raw = WorkspaceSettings.get(g.workspace_id, 'learned_insights')
    if insights_raw:
        try:
            learned_insights = json.loads(insights_raw)
        except Exception:
            pass

    claude = ClaudeService(api_key)

    try:
        if template_id:
            # Template-based generation
            template = Template.query.get(template_id)
            if not template:
                return jsonify({'error': 'Template not found'}), 404

            # Build recipient dict matching what personalize_email expects
            recipient_data = {
                'name': recipient.get('name', ''),
                'email': recipient.get('email', ''),
                'company': recipient.get('company', ''),
                'custom_fields': {}
            }

            # Add notes as context custom field
            if recipient.get('notes'):
                recipient_data['custom_fields']['context'] = recipient['notes']

            # Add explicit custom_fields from frontend (template variable values)
            frontend_custom = data.get('custom_fields', {})
            if frontend_custom:
                recipient_data['custom_fields'].update(frontend_custom)

            # Add any other top-level fields the user provided
            for key in recipient:
                if key not in ('name', 'email', 'company', 'notes'):
                    recipient_data['custom_fields'][key] = recipient[key]

            # Fetch website insights
            website_insights = None
            website_status = None
            try:
                from app.services.website_analyzer import WebsiteAnalyzer
                url = WebsiteAnalyzer.resolve_url(recipient_data)
                if url:
                    current_app.logger.info(f'Fetching website: {url}')
                    text = WebsiteAnalyzer.fetch_website(url)
                    if text and len(text) >= 50:
                        company = recipient_data.get('company') or url
                        website_insights = claude.analyze_website(text, company, url)
                        website_status = 'success'
                        current_app.logger.info(f'Website analysis complete for {url}')
                    else:
                        website_status = 'fetch_failed'
                        current_app.logger.warning(
                            f'Website fetch returned no/insufficient content for {url}'
                        )
                else:
                    website_status = 'no_url'
                    current_app.logger.info('No website URL resolved for recipient')
            except Exception as e:
                website_status = 'error'
                current_app.logger.warning(f'Website analysis failed: {e}')

            result = claude.personalize_email(
                template_subject=template.subject,
                template_body=template.body,
                recipient=recipient_data,
                custom_prompt=context or None,
                writing_style=writing_style,
                campaign_context=None,
                website_insights=website_insights,
                learned_insights=learned_insights
            )
            result['website_status'] = website_status
            return jsonify(result)
        else:
            # Freeform generation (no template)
            result = claude.generate_quick_email(
                recipient=recipient,
                context=context,
                writing_style=writing_style_raw,
                learned_insights=learned_insights
            )
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@quick_send_bp.route('/send', methods=['POST'])
def send_quick_email():
    """Send a one-off email."""
    data = request.get_json()

    to = data.get('to')
    subject = data.get('subject')
    body = data.get('body')
    account_id = data.get('account_id')

    if not to or not subject or not body:
        return jsonify({'error': 'To, subject, and body are required'}), 400

    # Resolve attachments from IDs
    attachment_list = _resolve_attachments(data.get('attachments', []))

    # Verify account exists if specified
    if account_id:
        account = OAuthToken.get_by_id(account_id)
        if not account:
            return jsonify({'error': 'Selected Gmail account not found'}), 400
    else:
        account = OAuthToken.get_default_gmail()
        if not account:
            return jsonify({'error': 'No Gmail account connected'}), 400

    gmail = GmailService(account_id=account_id)
    if not gmail.connect():
        return jsonify({'error': 'Gmail not connected'}), 400

    tracking_id = TrackingService.generate_tracking_id()
    base_url = current_app.config.get('TRACKING_BASE_URL', 'http://localhost:5001')

    result = gmail.send_email(
        to=to,
        subject=subject,
        body=body,
        html=True,
        tracking_id=tracking_id,
        base_url=base_url,
        attachments=attachment_list or None,
    )

    if result.get('success'):
        # Create EmailLog for tracking
        log = EmailLog(
            workspace_id=g.workspace_id,
            gmail_message_id=result.get('message_id'),
            gmail_thread_id=result.get('thread_id'),
            gmail_account_id=account.id,
            recipient_email=to,
            tracking_id=tracking_id,
            subject=subject,
            body=body,
            status='sent',
            is_html=True,
            link_map=json.dumps(result.get('link_map') or {}),
        )
        db.session.add(log)

        # Auto-add/update contact directory
        from app.models.contact import Contact
        Contact.upsert_from_send(
            email=to,
            name=data.get('recipient_name'),
            company=data.get('recipient_company'),
            website=data.get('recipient_website'),
            workspace_id=g.workspace_id,
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message_id': result.get('message_id'),
            'sent_from': account.email_address
        })
    else:
        return jsonify({'error': result.get('error', 'Failed to send email')}), 500
