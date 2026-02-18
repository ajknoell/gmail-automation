from flask import Blueprint, request, jsonify, Response, current_app, g
from app import db
from app.models import Campaign, Recipient, Template, EmailLog, Settings, OAuthToken
from app.models.campaign_step import CampaignStep
from app.models.step_recipient import StepRecipient
from app.models.settings import WorkspaceSettings
from app.services.csv_parser import parse_file, detect_field_mapping, detect_address_column, parse_address
from app.services.claude_service import ClaudeService, clean_company_name, _looks_like_company_name, resolve_recipient_fields
from app.services.campaign_runner import CampaignRunner
from app.services.spam_checker import check_spam_score
import re
from datetime import datetime
import json
import csv
import io
import os

campaigns_bp = Blueprint('campaigns', __name__)

@campaigns_bp.route('/sample-csv', methods=['GET'])
def download_sample_csv():
    """Download sample CSV template for founder outreach."""
    sample_data = '''email,name,company,title,industry,company_size,funding_stage,recent_news,pain_points,linkedin_url,referral,context
john@acmestartup.com,John Smith,Acme Startup,Founder & CEO,SaaS / B2B,15 employees,Series A,"Just announced $5M Series A in TechCrunch",Scaling sales team while maintaining product quality,https://linkedin.com/in/johnsmith,Met at SaaStr 2024,"John spoke at SaaStr about bootstrapping to $1M ARR. Passionate about developer tools. Previously worked at Stripe."
sarah@healthtechco.io,Sarah Chen,HealthTech Co,Co-Founder,Healthcare Technology,50 employees,Series B,"Launched new telemedicine platform last month",HIPAA compliance and enterprise sales cycles,https://linkedin.com/in/sarahchen,Referred by Mike at Sequoia,"Sarah is a repeat founder - sold her first company to Philips. Very data-driven, appreciates metrics in conversations."
'''
    return Response(
        sample_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sample_founder_outreach.csv'}
    )

@campaigns_bp.route('', methods=['GET'])
def list_campaigns():
    """List all campaigns."""
    campaigns = Campaign.query.filter_by(workspace_id=g.workspace_id).order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in campaigns])

@campaigns_bp.route('/<int:id>', methods=['GET'])
def get_campaign(id):
    """Get a single campaign with stats and steps."""
    campaign = Campaign.query.get_or_404(id)
    return jsonify(campaign.to_dict(include_template=True, include_steps=True))

@campaigns_bp.route('', methods=['POST'])
def create_campaign():
    """Create a new campaign."""
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    # Get gmail_account_id from request or use default
    gmail_account_id = data.get('gmail_account_id')
    if not gmail_account_id:
        default_account = OAuthToken.get_default_gmail()
        gmail_account_id = default_account.id if default_account else None

    campaign = Campaign(
        workspace_id=g.workspace_id,
        name=data['name'],
        template_id=data.get('template_id'),
        gmail_account_id=gmail_account_id,
        delay_seconds=data.get('delay_seconds', 30),
        use_ai_personalization=data.get('use_ai_personalization', True),
        ai_prompt=data.get('ai_prompt'),
        campaign_context=data.get('campaign_context'),
        competitor_search_query=data.get('competitor_search_query'),
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
    if 'gmail_account_id' in data:
        campaign.gmail_account_id = data['gmail_account_id']
    if 'delay_seconds' in data:
        campaign.delay_seconds = data['delay_seconds']
    if 'use_ai_personalization' in data:
        campaign.use_ai_personalization = data['use_ai_personalization']
    if 'ai_prompt' in data:
        campaign.ai_prompt = data['ai_prompt']
    if 'campaign_context' in data:
        campaign.campaign_context = data['campaign_context']
    if 'competitor_search_query' in data:
        campaign.competitor_search_query = data['competitor_search_query']
    if 'attachments' in data:
        campaign.set_attachments(data['attachments'])

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

        # Validate that an email column was detected
        if 'email' not in mapping:
            return jsonify({
                'error': f'Could not detect an email column in your file. Found columns: {", ".join(headers)}. '
                         f'Please ensure your file has a column with "email" in the header name.',
                'headers': headers,
                'mapping': mapping
            }), 400

        if not rows:
            return jsonify({'error': 'File contains no data rows'}), 400

        # Detect address column for auto-splitting into street/city/state/zip
        address_col = detect_address_column(headers)

        # Build map of existing emails to recipient objects for duplicate detection
        existing_recipients = {
            r.email.lower(): r
            for r in Recipient.query.filter_by(campaign_id=id).all()
        }

        # Import recipients, updating duplicates with new data
        added = 0
        updated = 0
        skipped_invalid = 0

        for row in rows:
            email = row.get(mapping.get('email', ''), '').strip()
            if not email or '@' not in email:
                skipped_invalid += 1
                continue

            name = row.get(mapping.get('name', ''), '')
            company = row.get(mapping.get('company', ''), '')
            custom = {k: v for k, v in row.items()
                     if k not in [mapping.get('email'), mapping.get('name'), mapping.get('company')]}

            # Auto-split address column into street/city/state/zip
            if address_col and address_col in custom:
                addr_parts = parse_address(custom[address_col])
                for field in ('street', 'city', 'state', 'zip'):
                    if field in addr_parts and field not in custom:
                        custom[field] = addr_parts[field]

            existing = existing_recipients.get(email.lower())
            if existing:
                # Update existing recipient with new data
                if name:
                    existing.name = name
                if company:
                    existing.company = company
                # Merge custom fields (new values override old ones)
                merged_custom = existing.get_custom_fields()
                merged_custom.update({k: v for k, v in custom.items() if v})
                existing.set_custom_fields(merged_custom)
                updated += 1
                continue

            recipient = Recipient(
                campaign_id=id,
                email=email,
                name=name,
                company=company,
            )
            recipient.set_custom_fields(custom)

            db.session.add(recipient)
            existing_recipients[email.lower()] = recipient
            added += 1

        # Use count() alone — autoflush ensures newly added recipients are included
        campaign.total_recipients = Recipient.query.filter_by(campaign_id=id).count()
        db.session.commit()

        if campaign.total_recipients == 0:
            return jsonify({
                'error': f'No valid email addresses found. {skipped_invalid} rows were skipped due to missing or invalid emails. '
                         f'Email column detected: "{mapping.get("email")}". Please check your file.',
                'headers': headers,
                'mapping': mapping
            }), 400

        return jsonify({
            'success': True,
            'headers': headers,
            'mapping': mapping,
            'total_recipients': campaign.total_recipients,
            'added': added,
            'updated': updated,
            'invalid_skipped': skipped_invalid,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@campaigns_bp.route('/<int:id>/recipients', methods=['DELETE'])
def clear_recipients(id):
    """Remove all recipients from a campaign (not while running)."""
    campaign = Campaign.query.get_or_404(id)
    if campaign.status == 'running':
        return jsonify({'error': 'Cannot clear recipients while campaign is running'}), 400

    # Get recipient IDs to clean up related records first
    recipient_ids = [r.id for r in Recipient.query.filter_by(campaign_id=id).with_entities(Recipient.id).all()]
    if recipient_ids:
        EmailLog.query.filter(EmailLog.recipient_id.in_(recipient_ids)).delete(synchronize_session=False)
        StepRecipient.query.filter(StepRecipient.recipient_id.in_(recipient_ids)).delete(synchronize_session=False)
        from app.models.website_analysis_log import WebsiteAnalysisLog
        WebsiteAnalysisLog.query.filter(WebsiteAnalysisLog.recipient_id.in_(recipient_ids)).delete(synchronize_session=False)
        from app.models.cold_call import ColdCall
        ColdCall.query.filter(ColdCall.recipient_id.in_(recipient_ids)).delete(synchronize_session=False)
    Recipient.query.filter_by(campaign_id=id).delete()
    campaign.total_recipients = 0
    db.session.commit()
    return jsonify({'success': True})


@campaigns_bp.route('/<int:id>/recipients/<int:recipient_id>', methods=['DELETE'])
def delete_recipient(id, recipient_id):
    """Remove a single recipient from a campaign (not while running)."""
    campaign = Campaign.query.get_or_404(id)
    if campaign.status == 'running':
        return jsonify({'error': 'Cannot remove recipients while campaign is running'}), 400

    recipient = Recipient.query.filter_by(id=recipient_id, campaign_id=id).first_or_404()
    # Clean up related records that have FK references to this recipient
    EmailLog.query.filter_by(recipient_id=recipient_id).delete()
    StepRecipient.query.filter_by(recipient_id=recipient_id).delete()
    from app.models.website_analysis_log import WebsiteAnalysisLog
    WebsiteAnalysisLog.query.filter_by(recipient_id=recipient_id).delete()
    from app.models.cold_call import ColdCall
    ColdCall.query.filter_by(recipient_id=recipient_id).delete()
    db.session.delete(recipient)
    campaign.total_recipients = max(0, (campaign.total_recipients or 0) - 1)
    db.session.commit()
    return jsonify({'success': True})


@campaigns_bp.route('/<int:id>/recipients/move', methods=['POST'])
def move_recipients(id):
    """Move pending recipients from this campaign to another campaign."""
    source = Campaign.query.get_or_404(id)

    if source.status != 'draft':
        return jsonify({'error': 'Can only move recipients from draft campaigns'}), 400

    data = request.get_json()
    recipient_ids = data.get('recipient_ids', [])
    target_campaign_id = data.get('target_campaign_id')
    new_campaign_name = data.get('new_campaign_name')

    if not recipient_ids:
        return jsonify({'error': 'No recipients selected'}), 400

    if not target_campaign_id and not new_campaign_name:
        return jsonify({'error': 'Target campaign or new campaign name is required'}), 400

    # Create new campaign if requested
    if new_campaign_name:
        target = Campaign(
            workspace_id=g.workspace_id,
            name=new_campaign_name.strip(),
        )
        db.session.add(target)
        db.session.flush()
    else:
        target = Campaign.query.get_or_404(target_campaign_id)
        if target.workspace_id != g.workspace_id:
            return jsonify({'error': 'Target campaign not found'}), 404

    if target.id == source.id:
        return jsonify({'error': 'Cannot move recipients to the same campaign'}), 400

    # Fetch selected recipients that belong to the source campaign
    recipients = Recipient.query.filter(
        Recipient.id.in_(recipient_ids),
        Recipient.campaign_id == id
    ).all()

    # Build set of existing emails in target for duplicate detection
    existing_emails = {
        r.email.lower()
        for r in Recipient.query.filter_by(campaign_id=target.id).all()
    }

    moved = 0
    skipped_sent = 0
    skipped_duplicate = 0

    for r in recipients:
        if r.status != 'pending':
            skipped_sent += 1
            continue

        if r.email.lower() in existing_emails:
            skipped_duplicate += 1
            continue

        r.campaign_id = target.id
        r.personalized_subject = None
        r.personalized_body = None
        r.approved = False
        r.error_message = None

        existing_emails.add(r.email.lower())
        moved += 1

    source.total_recipients = Recipient.query.filter_by(campaign_id=source.id).count()
    target.total_recipients = Recipient.query.filter_by(campaign_id=target.id).count()

    db.session.commit()

    return jsonify({
        'success': True,
        'moved': moved,
        'skipped_sent': skipped_sent,
        'skipped_duplicate': skipped_duplicate,
        'target_campaign_id': target.id,
        'target_campaign_name': target.name,
    })


@campaigns_bp.route('/<int:id>/recipients', methods=['GET'])
def list_recipients(id):
    """List recipients for a campaign with tracking data."""
    campaign = Campaign.query.get_or_404(id)
    recipients = Recipient.query.filter_by(campaign_id=id).all()

    # Join tracking data from email logs
    logs = EmailLog.query.filter_by(campaign_id=id).all()
    tracking_by_recipient = {l.recipient_id: l for l in logs}

    # Join website analysis severity data
    from app.models.website_analysis_log import WebsiteAnalysisLog
    recipient_ids = [r.id for r in recipients]
    severity_map = {}
    if recipient_ids:
        analysis_logs = WebsiteAnalysisLog.query.filter(
            WebsiteAnalysisLog.recipient_id.in_(recipient_ids)
        ).all()
        for al in analysis_logs:
            # Keep the most recent analysis per recipient
            if al.recipient_id not in severity_map or (al.created_at and severity_map[al.recipient_id].get('_created_at', '') < al.created_at.isoformat()):
                severity_map[al.recipient_id] = {
                    'max_severity': al.max_severity,
                    '_created_at': al.created_at.isoformat() if al.created_at else '',
                }

    result = []
    for r in recipients:
        data = r.to_dict()
        log = tracking_by_recipient.get(r.id)
        if log:
            data['tracking'] = {
                'opened_at': log.opened_at.isoformat() if log.opened_at else None,
                'open_count': log.open_count or 0,
                'clicked_at': log.clicked_at.isoformat() if log.clicked_at else None,
                'click_count': log.click_count or 0,
                'replied_at': log.replied_at.isoformat() if log.replied_at else None,
                'bounced_at': log.bounced_at.isoformat() if log.bounced_at else None,
                'bounce_reason': log.bounce_reason,
            }
        # Include per-recipient spam check when content exists
        if r.personalized_body:
            data['spam_check'] = check_spam_score(
                r.personalized_subject or '', r.personalized_body
            )
        # Surface content warnings (stored in error_message during generation)
        if r.error_message and r.personalized_body:
            data['content_warnings'] = r.error_message.split(' | ')
        # Include website analysis severity
        sev_data = severity_map.get(r.id)
        if sev_data:
            data['website_severity'] = sev_data['max_severity']
        result.append(data)

    return jsonify(result)

@campaigns_bp.route('/<int:id>/recipients/<int:recipient_id>', methods=['PUT'])
def update_recipient(id, recipient_id):
    """Update a recipient (notes, personalized content)."""
    recipient = Recipient.query.filter_by(id=recipient_id, campaign_id=id).first_or_404()
    data = request.get_json()

    if 'notes' in data:
        recipient.notes = data['notes']
    if 'personalized_subject' in data:
        recipient.personalized_subject = data['personalized_subject']
    if 'personalized_body' in data:
        recipient.personalized_body = data['personalized_body']
    if 'approved' in data:
        recipient.approved = data['approved']

    db.session.commit()
    return jsonify(recipient.to_dict())

def _get_writing_style():
    """Helper to get writing style from workspace settings (fallback to global)."""
    style_json = WorkspaceSettings.get(g.workspace_id, 'writing_style')
    if not style_json:
        style_json = Settings.get('writing_style')
    if style_json:
        try:
            return json.loads(style_json)
        except:
            pass
    return None

def _get_learned_insights():
    """Helper to get learned insights from workspace settings."""
    insights_json = WorkspaceSettings.get(g.workspace_id, 'learned_insights')
    if insights_json:
        try:
            return json.loads(insights_json)
        except:
            pass
    return None

def _get_learned_website_insights():
    """Helper to get learned website analysis insights from workspace settings."""
    raw = WorkspaceSettings.get(g.workspace_id, 'learned_website_insights')
    if raw:
        try:
            return json.loads(raw)
        except:
            pass
    return None

def _log_website_analysis(workspace_id, recipient_id, result):
    """Log a website analysis result for the learning feedback loop."""
    from app.models.website_analysis_log import WebsiteAnalysisLog
    analysis_data = result.get('analysis')
    analysis_json_str = None
    max_severity = None
    if analysis_data and isinstance(analysis_data, dict):
        analysis_json_str = json.dumps(analysis_data)
        max_severity = ClaudeService.get_max_severity(analysis_data)
    log = WebsiteAnalysisLog(
        workspace_id=workspace_id,
        recipient_id=recipient_id,
        url=result['url'],
        company=result.get('company'),
        raw_text_preview=result.get('raw_text_preview'),
        analysis_result=result.get('analysis_text', ''),
        analysis_json=analysis_json_str,
        max_severity=max_severity,
    )
    db.session.add(log)
    return log

@campaigns_bp.route('/<int:id>/recipients/<int:recipient_id>/regenerate', methods=['POST'])
def regenerate_recipient_preview(id, recipient_id):
    """Regenerate AI preview for a single recipient."""
    campaign = Campaign.query.get_or_404(id)
    recipient = Recipient.query.filter_by(id=recipient_id, campaign_id=id).first_or_404()

    if not campaign.template:
        return jsonify({'error': 'No template selected'}), 400

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    claude = ClaudeService(api_key)
    writing_style = _get_writing_style()
    learned_insights = _get_learned_insights()

    try:
        # Fetch and analyze recipient's website
        # Pass previous observations so the model picks different angles on regeneration
        from app.services.website_analyzer import WebsiteAnalyzer
        learned_website_insights = _get_learned_website_insights()
        recipient_dict = {
            'name': recipient.name,
            'email': recipient.email,
            'company': recipient.company,
            'custom_fields': recipient.get_all_context()
        }
        # Extract the observation from the previous email body for regeneration.
        # Body is HTML with <br> tags instead of newlines, so normalize first.
        previous_observations = None
        if recipient.personalized_body:
            import re as _re
            # Convert HTML breaks to newlines so line-based regex can work
            plain = _re.sub(r'<br\s*/?\s*>', '\n', recipient.personalized_body)
            obs_lines = _re.findall(r'^\s*1\.\s*.+', plain, _re.MULTILINE)
            if obs_lines:
                # Strip any remaining HTML tags from extracted observation
                previous_observations = _re.sub(r'<[^>]+>', '', obs_lines[0])
        wa_result = WebsiteAnalyzer.fetch_and_analyze(
            claude, recipient_dict, learned_website_insights,
            previous_observations=previous_observations,
        )
        website_insights = wa_result.get('analysis_text') if wa_result else None
        website_analysis_data = wa_result.get('analysis') if wa_result else None
        team_contacts = wa_result.get('team_contacts', []) if wa_result else []

        # Log the analysis for learning
        if wa_result:
            _log_website_analysis(g.workspace_id, recipient.id, wa_result)

        # Competitor discovery
        competitors = []
        if campaign.competitor_search_query:
            tavily_key = Settings.get('tavily_api_key')
            if tavily_key:
                from app.services.web_search import WebSearchService
                from app.services.competitor_discovery import CompetitorService
                comp_svc = CompetitorService(WebSearchService(tavily_key), claude)
                custom_fields = recipient_dict.get('custom_fields', {})
                competitors = comp_svc.discover_competitors(
                    company=recipient_dict.get('company', ''),
                    domain=(wa_result.get('url') if wa_result else '') or recipient.email or '',
                    industry=custom_fields.get('industry') or custom_fields.get('sector', ''),
                    search_query=campaign.competitor_search_query,
                    custom_fields=custom_fields,
                )

        result = claude.personalize_email(
            template_subject=campaign.template.subject,
            template_body=campaign.template.body,
            recipient=recipient_dict,
            custom_prompt=campaign.ai_prompt,
            writing_style=writing_style,
            campaign_context=campaign.campaign_context,
            website_insights=website_insights,
            learned_insights=learned_insights,
            team_contacts=team_contacts,
            competitors=competitors,
        )
        recipient.personalized_subject = result.get('subject', campaign.template.subject)
        recipient.personalized_body = result.get('body', campaign.template.body)
        recipient.approved = False  # Reset approval after regeneration
        # Build content warnings including severity-based flags
        content_warnings = result.get('content_warnings', [])
        if website_analysis_data:
            severity = ClaudeService.get_max_severity(website_analysis_data)
            if not severity:
                content_warnings.append('No significant website issues found for outreach')
        if content_warnings:
            recipient.error_message = ' | '.join(content_warnings)
        else:
            recipient.error_message = None
        db.session.commit()

        resp = recipient.to_dict()
        resp['spam_check'] = check_spam_score(
            recipient.personalized_subject, recipient.personalized_body
        )
        if website_analysis_data:
            resp['website_severity'] = ClaudeService.get_max_severity(website_analysis_data)
        if recipient.error_message and recipient.personalized_body:
            resp['content_warnings'] = recipient.error_message.split(' | ')
        return jsonify(resp)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _substitute_template_variables(text, recipient, extra_variables=None):
    """Replace {{variable}} placeholders with recipient data."""
    custom = recipient.get_custom_fields() or {}
    name, company = resolve_recipient_fields(
        recipient.name, clean_company_name(recipient.company or ''),
        recipient.email, custom,
    )
    variables = {
        'name': name or 'there',
        'email': recipient.email or '',
        'company': company or '',
    }
    if custom:
        variables.update(custom)
    if extra_variables:
        variables.update(extra_variables)

    def replace_var(match):
        key = match.group(1)
        # Support fallback syntax: {{city|state}} tries city first, then state
        for part in key.split('|'):
            part = part.strip()
            val = variables.get(part, '')
            if val:
                return val
        return match.group(0)

    return re.sub(r'\{\{([\w| ]+)\}\}', replace_var, text)


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

    if not unpersonalized:
        return jsonify({'success': True, 'generated': 0, 'failed': 0, 'remaining': 0, 'message': 'All emails already generated'})

    if batch_size > 0:
        recipients = unpersonalized[:batch_size]
    else:
        recipients = unpersonalized

    remaining = len(unpersonalized) - len(recipients) if batch_size > 0 else 0

    from app.services.website_analyzer import WebsiteAnalyzer

    generated = 0
    failed = 0

    if campaign.use_ai_personalization:
        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return jsonify({'error': 'Anthropic API key not configured'}), 400

        claude = ClaudeService(api_key)
        writing_style = _get_writing_style()
        learned_insights = _get_learned_insights()
        learned_website_insights = _get_learned_website_insights()

        # Cache website analysis by resolved URL so recipients at the same
        # domain don't trigger duplicate fetches / screenshots / API calls.
        website_analysis_cache = {}

        # Competitor discovery service (opt-in per campaign)
        competitor_service = None
        if campaign.competitor_search_query:
            tavily_key = Settings.get('tavily_api_key')
            if tavily_key:
                from app.services.web_search import WebSearchService
                from app.services.competitor_discovery import CompetitorService
                competitor_service = CompetitorService(WebSearchService(tavily_key), claude)

        for recipient in recipients:
            try:
                recipient_dict = {
                    'name': recipient.name,
                    'email': recipient.email,
                    'company': recipient.company,
                    'custom_fields': recipient.get_all_context()
                }

                # Domain-level caching for website analysis
                resolved_url = WebsiteAnalyzer.resolve_url(recipient_dict)
                cache_key = (resolved_url or '').lower().rstrip('/')
                if cache_key and cache_key in website_analysis_cache:
                    wa_result = website_analysis_cache[cache_key]
                else:
                    wa_result = WebsiteAnalyzer.fetch_and_analyze(claude, recipient_dict, learned_website_insights)
                    if cache_key and wa_result:
                        website_analysis_cache[cache_key] = wa_result
                website_insights = wa_result.get('analysis_text') if wa_result else None
                website_analysis_data = wa_result.get('analysis') if wa_result else None
                team_contacts = wa_result.get('team_contacts', []) if wa_result else []

                # Log the analysis for the learning feedback loop
                if wa_result:
                    _log_website_analysis(g.workspace_id, recipient.id, wa_result)

                # Competitor discovery (cached per resolved query)
                competitors = []
                if competitor_service:
                    custom_fields = recipient_dict.get('custom_fields', {})
                    competitors = competitor_service.discover_competitors(
                        company=recipient_dict.get('company', ''),
                        domain=cache_key or recipient.email or '',
                        industry=custom_fields.get('industry') or custom_fields.get('sector', ''),
                        search_query=campaign.competitor_search_query,
                        custom_fields=custom_fields,
                    )

                result = claude.personalize_email(
                    template_subject=campaign.template.subject,
                    template_body=campaign.template.body,
                    recipient=recipient_dict,
                    custom_prompt=campaign.ai_prompt,
                    writing_style=writing_style,
                    campaign_context=campaign.campaign_context,
                    website_insights=website_insights,
                    learned_insights=learned_insights,
                    team_contacts=team_contacts,
                    competitors=competitors,
                )
                recipient.personalized_subject = result.get('subject', campaign.template.subject)
                recipient.personalized_body = result.get('body', campaign.template.body)
                # Build content warnings including severity-based flags
                content_warnings = result.get('content_warnings', [])
                if website_analysis_data:
                    severity = ClaudeService.get_max_severity(website_analysis_data)
                    if not severity:
                        content_warnings.append('No significant website issues found for outreach')
                if content_warnings:
                    recipient.error_message = ' | '.join(content_warnings)
                else:
                    recipient.error_message = None
                generated += 1
            except Exception as e:
                # Do NOT set personalized_body on failure — leave the recipient
                # in the unpersonalized pool so they can be retried next batch.
                current_app.logger.warning(
                    f"Failed to personalize recipient {recipient.id} ({recipient.email}): {e}"
                )
                failed += 1
            # Commit after each to preserve progress
            db.session.commit()
    else:
        # Simple {{variable}} substitution without AI
        # Set up competitor discovery for non-AI path too
        non_ai_comp_service = None
        non_ai_comp_cache = {}
        if campaign.competitor_search_query:
            tavily_key = Settings.get('tavily_api_key')
            if tavily_key:
                from app.services.web_search import WebSearchService
                from app.services.competitor_discovery import CompetitorService
                non_ai_comp_service = CompetitorService(WebSearchService(tavily_key))

        for recipient in recipients:
            extra_vars = None
            if non_ai_comp_service:
                from app.services.website_analyzer import WebsiteAnalyzer as _WA
                comp_key = (_WA.resolve_url({
                    'email': recipient.email,
                    'custom_fields': recipient.get_custom_fields(),
                }) or recipient.email or '').lower()
                if comp_key not in non_ai_comp_cache:
                    cf = recipient.get_custom_fields()
                    non_ai_comp_cache[comp_key] = non_ai_comp_service.discover_competitors(
                        company=recipient.company or '',
                        domain=comp_key,
                        industry=cf.get('industry') or cf.get('sector', ''),
                        search_query=campaign.competitor_search_query,
                        custom_fields=cf,
                    )
                comps = non_ai_comp_cache.get(comp_key, [])
                if comps:
                    extra_vars = CompetitorService.build_variable_map(comps)

            recipient.personalized_subject = _substitute_template_variables(
                campaign.template.subject, recipient, extra_vars)
            recipient.personalized_body = _substitute_template_variables(
                campaign.template.body, recipient, extra_vars)
            generated += 1
        db.session.commit()

    # Run spam check on all generated recipients and flag any issues
    spam_warnings = 0
    for recipient in recipients:
        if recipient.personalized_body:
            sc = check_spam_score(
                recipient.personalized_subject or '', recipient.personalized_body
            )
            if sc['level'] in ('medium', 'high'):
                spam_warnings += 1

    return jsonify({
        'success': True,
        'generated': generated,
        'failed': failed,
        'remaining': remaining,
        'spam_warnings': spam_warnings,
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
    from app.services.tracking_service import TrackingService

    account_id = campaign.gmail_account_id
    if account_id:
        account = OAuthToken.get_by_id(account_id)
    else:
        account = OAuthToken.get_default_gmail()
    if not account:
        return jsonify({'error': 'No Gmail account connected'}), 400

    gmail = GmailService(account_id=account.id)
    if not gmail.connect():
        return jsonify({'error': 'Gmail not connected'}), 400

    subject = recipient.personalized_subject or 'No subject'
    body = recipient.personalized_body

    # Load campaign attachments
    campaign_attachments = None
    att_list = campaign.get_attachments()
    if att_list:
        from app.routes.quick_send import _resolve_attachments
        campaign_attachments = _resolve_attachments(att_list) or None

    tracking_id = TrackingService.generate_tracking_id()
    base_url = current_app.config.get('TRACKING_BASE_URL', 'http://localhost:5001')

    result = gmail.send_email(
        to=recipient.email,
        subject=subject,
        body=body,
        html=True,
        tracking_id=tracking_id,
        base_url=base_url,
        attachments=campaign_attachments,
    )

    if result.get('success'):
        recipient.status = 'sent'
        recipient.sent_at = datetime.utcnow()
        campaign.sent_count += 1

        log = EmailLog(
            workspace_id=g.workspace_id,
            recipient_id=recipient.id,
            campaign_id=id,
            gmail_message_id=result.get('message_id'),
            gmail_thread_id=result.get('thread_id'),
            gmail_account_id=account.id,
            recipient_email=recipient.email,
            tracking_id=tracking_id,
            subject=subject,
            body=body,
            status='sent',
            is_html=True,
            link_map=json.dumps(result.get('link_map') or {}),
        )
        db.session.add(log)
        db.session.flush()  # Get log.id before commit

        # Link website analysis log to this email for the learning loop
        from app.models.website_analysis_log import WebsiteAnalysisLog
        wa_log = (
            WebsiteAnalysisLog.query
            .filter_by(workspace_id=g.workspace_id, recipient_id=recipient.id, email_log_id=None)
            .order_by(WebsiteAnalysisLog.created_at.desc())
            .first()
        )
        if wa_log:
            wa_log.email_log_id = log.id

        db.session.commit()

        return jsonify({'success': True, 'status': 'sent'})
    else:
        error = result.get('error', 'Unknown error')
        recipient.status = 'failed'
        recipient.error_message = error
        campaign.failed_count += 1

        log = EmailLog(
            workspace_id=g.workspace_id,
            recipient_id=recipient.id,
            campaign_id=id,
            recipient_email=recipient.email,
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

    # Check for recipients without generated content
    ungenerated = [r for r in recipients if not r.personalized_body or not r.personalized_body.strip()]
    if ungenerated:
        force = request.get_json() and request.get_json().get('force')
        if not force:
            return jsonify({
                'error': f'{len(ungenerated)} of {len(recipients)} approved recipients do not have generated email content. Generate previews first, or start with force=true to skip those recipients.',
                'ungenerated_count': len(ungenerated),
                'total_approved': len(recipients)
            }), 400

    # Verify Gmail account is available
    account_id = campaign.gmail_account_id
    if account_id:
        account = OAuthToken.get_by_id(account_id)
        if not account:
            return jsonify({'error': 'Selected Gmail account no longer exists'}), 400
    else:
        account = OAuthToken.get_default_gmail()
        if not account:
            return jsonify({'error': 'No Gmail account connected'}), 400
        account_id = account.id

    campaign.status = 'running'
    campaign.started_at = datetime.utcnow()
    db.session.commit()

    # Start campaign runner in background with account_id
    CampaignRunner.start(campaign.id, [r.id for r in recipients], campaign.delay_seconds, account_id)

    return jsonify({'success': True, 'status': 'running', 'sending_from': account.email_address})

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

    if campaign.status not in ['running', 'paused', 'sequence_active']:
        return jsonify({'error': 'Campaign is not active'}), 400

    CampaignRunner.cancel(id)

    # Cancel any pending steps
    CampaignStep.query.filter(
        CampaignStep.campaign_id == id,
        CampaignStep.status.notin_(['completed', 'cancelled']),
    ).update({'status': 'cancelled'}, synchronize_session=False)

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

    # Build tracking lookup by recipient_id
    logs = EmailLog.query.filter_by(campaign_id=id).all()
    tracking_by_recipient = {l.recipient_id: l for l in logs}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Name', 'Company', 'Status', 'Sent At',
                      'Opened At', 'Open Count', 'Clicked At', 'Click Count',
                      'Replied At', 'Error'])

    for r in recipients:
        log = tracking_by_recipient.get(r.id)
        writer.writerow([
            r.email,
            r.name,
            r.company,
            r.status,
            r.sent_at.isoformat() if r.sent_at else '',
            log.opened_at.isoformat() if log and log.opened_at else '',
            log.open_count if log else 0,
            log.clicked_at.isoformat() if log and log.clicked_at else '',
            log.click_count if log else 0,
            log.replied_at.isoformat() if log and log.replied_at else '',
            r.error_message or ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=campaign_{id}_results.csv'}
    )


# ---- Campaign Steps API ----

@campaigns_bp.route('/<int:id>/steps', methods=['GET'])
def list_steps(id):
    """List all steps for a campaign."""
    Campaign.query.get_or_404(id)
    steps = CampaignStep.query.filter_by(campaign_id=id).order_by(CampaignStep.position).all()
    return jsonify([s.to_dict() for s in steps])


@campaigns_bp.route('/<int:id>/steps', methods=['POST'])
def create_step(id):
    """Add a new step to a campaign."""
    campaign = Campaign.query.get_or_404(id)
    if campaign.status in ('running',):
        return jsonify({'error': 'Cannot add steps to a running campaign'}), 400

    data = request.get_json()

    max_pos = db.session.query(db.func.max(CampaignStep.position)).filter_by(
        campaign_id=id
    ).scalar() or 0

    requested_pos = data.get('position')
    if requested_pos and requested_pos <= max_pos:
        # Insert: shift existing steps up
        CampaignStep.query.filter(
            CampaignStep.campaign_id == id,
            CampaignStep.position >= requested_pos,
        ).update({CampaignStep.position: CampaignStep.position + 1})
        position = requested_pos
    else:
        position = max_pos + 1

    step = CampaignStep(
        campaign_id=id,
        position=position,
        name=data.get('name') or f'Follow-up #{position - 1}' if position > 1 else 'Initial Outreach',
        step_type=data.get('step_type', 'ai_followup'),
        template_id=data.get('template_id'),
        ai_prompt=data.get('ai_prompt'),
        delay_days=data.get('delay_days', 3),
        use_web_research=data.get('use_web_research', False),
        web_research_prompt=data.get('web_research_prompt'),
        auto_send=data.get('auto_send', False),
    )
    db.session.add(step)
    db.session.commit()

    # Create StepRecipient entries for all campaign recipients
    _populate_step_recipients(step)

    return jsonify(step.to_dict()), 201


@campaigns_bp.route('/<int:id>/steps/<int:step_id>', methods=['PUT'])
def update_step(id, step_id):
    """Update a step's configuration."""
    Campaign.query.get_or_404(id)
    step = CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    if step.status in ('running',):
        return jsonify({'error': 'Cannot update a running step'}), 400

    data = request.get_json()

    if 'name' in data:
        step.name = data['name']
    if 'step_type' in data:
        step.step_type = data['step_type']
    if 'template_id' in data:
        step.template_id = data['template_id']
    if 'ai_prompt' in data:
        step.ai_prompt = data['ai_prompt']
    if 'delay_days' in data:
        step.delay_days = data['delay_days']
    if 'use_web_research' in data:
        step.use_web_research = data['use_web_research']
    if 'web_research_prompt' in data:
        step.web_research_prompt = data['web_research_prompt']
    if 'auto_send' in data:
        step.auto_send = data['auto_send']

    db.session.commit()
    return jsonify(step.to_dict())


@campaigns_bp.route('/<int:id>/steps/<int:step_id>', methods=['DELETE'])
def delete_step(id, step_id):
    """Delete a step and reorder remaining steps."""
    Campaign.query.get_or_404(id)
    step = CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    if step.status == 'running':
        return jsonify({'error': 'Cannot delete a running step'}), 400

    position = step.position
    db.session.delete(step)

    # Reorder: shift positions down for steps after the deleted one
    CampaignStep.query.filter(
        CampaignStep.campaign_id == id,
        CampaignStep.position > position,
    ).update({CampaignStep.position: CampaignStep.position - 1})

    db.session.commit()
    return jsonify({'success': True})


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/recipients', methods=['GET'])
def list_step_recipients(id, step_id):
    """List step recipients with status and tracking data."""
    Campaign.query.get_or_404(id)
    CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    step_recipients = StepRecipient.query.filter_by(step_id=step_id).all()

    # Join tracking data from email logs
    log_ids = [sr.email_log_id for sr in step_recipients if sr.email_log_id]
    logs_by_id = {}
    if log_ids:
        logs = EmailLog.query.filter(EmailLog.id.in_(log_ids)).all()
        logs_by_id = {l.id: l for l in logs}

    result = []
    for sr in step_recipients:
        data = sr.to_dict()
        if sr.email_log_id and sr.email_log_id in logs_by_id:
            log = logs_by_id[sr.email_log_id]
            data['tracking'] = {
                'opened_at': log.opened_at.isoformat() if log.opened_at else None,
                'open_count': log.open_count or 0,
                'clicked_at': log.clicked_at.isoformat() if log.clicked_at else None,
                'click_count': log.click_count or 0,
                'replied_at': log.replied_at.isoformat() if log.replied_at else None,
                'bounced_at': log.bounced_at.isoformat() if log.bounced_at else None,
            }
        result.append(data)

    return jsonify(result)


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/generate-preview', methods=['POST'])
def generate_step_preview(id, step_id):
    """Generate AI-personalized content for a step's recipients."""
    campaign = Campaign.query.get_or_404(id)
    step = CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    data = request.get_json(silent=True) or {}
    batch_size = data.get('batch_size', 50)

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    claude = ClaudeService(api_key)
    writing_style = _get_writing_style()
    learned_insights = _get_learned_insights()

    # Web search service if needed
    web_search = None
    if step.use_web_research:
        tavily_key = Settings.get('tavily_api_key')
        if tavily_key:
            from app.services.web_search import WebSearchService
            web_search = WebSearchService(tavily_key)

    # Find step recipients that need generation
    unpersonalized = (
        StepRecipient.query
        .filter_by(step_id=step_id, status='pending')
        .filter(StepRecipient.personalized_body.is_(None))
        .limit(batch_size if batch_size > 0 else 10000)
        .all()
    )

    step.status = 'generating'
    db.session.commit()

    generated = 0
    failed = 0

    for sr in unpersonalized:
        recipient = Recipient.query.get(sr.recipient_id)
        if not recipient:
            continue

        try:
            if step.step_type == 'ai_followup':
                # Build conversation history from prior steps
                conversation_history = _build_conversation_history(campaign.id, recipient.id, step.position)

                # Web research
                research_text = None
                if web_search and step.use_web_research:
                    custom_fields = recipient.get_custom_fields()
                    from app.services.web_search import WebSearchService
                    research = web_search.research_company(
                        company=recipient.company or '',
                        industry=custom_fields.get('industry') or custom_fields.get('sector'),
                        custom_query=step.web_research_prompt,
                        recipient_name=recipient.name,
                    )
                    research_text = WebSearchService.format_for_prompt(research)
                    sr.web_research_results = json.dumps(research)

                original_subject = _get_original_subject(campaign.id, recipient.id)

                result = claude.generate_sequence_followup(
                    step_number=step.position,
                    original_subject=original_subject,
                    conversation_history=conversation_history,
                    contact_info={
                        'name': recipient.name,
                        'company': recipient.company,
                    },
                    ai_prompt=step.ai_prompt,
                    campaign_context=campaign.campaign_context,
                    web_research=research_text,
                    writing_style=writing_style,
                    learned_insights=learned_insights,
                )
                sr.personalized_subject = result.get('subject', f'Re: {original_subject}')
                sr.personalized_body = result.get('body', '')
                sr.status = 'ready'
                generated += 1

            elif step.step_type == 'template' and step.template_id:
                # Reuse existing personalization flow
                template = Template.query.get(step.template_id)
                if not template:
                    sr.status = 'failed'
                    sr.error_message = 'Template not found'
                    failed += 1
                    db.session.commit()
                    continue

                if campaign.use_ai_personalization:
                    recipient_dict = {
                        'name': recipient.name,
                        'email': recipient.email,
                        'company': recipient.company,
                        'custom_fields': recipient.get_all_context()
                    }
                    result = claude.personalize_email(
                        template_subject=template.subject,
                        template_body=template.body,
                        recipient=recipient_dict,
                        custom_prompt=campaign.ai_prompt,
                        writing_style=writing_style,
                        campaign_context=campaign.campaign_context,
                        learned_insights=learned_insights,
                    )
                    sr.personalized_subject = result.get('subject', template.subject)
                    sr.personalized_body = result.get('body', template.body)
                else:
                    sr.personalized_subject = _substitute_template_variables(template.subject, recipient)
                    sr.personalized_body = _substitute_template_variables(template.body, recipient)

                sr.status = 'ready'
                generated += 1

            db.session.commit()

        except Exception as e:
            current_app.logger.warning(f"Failed to generate step content for recipient {recipient.id}: {e}")
            sr.error_message = str(e)
            failed += 1
            db.session.commit()

    # Update step status
    remaining = (
        StepRecipient.query
        .filter_by(step_id=step_id, status='pending')
        .filter(StepRecipient.personalized_body.is_(None))
        .count()
    )
    if remaining == 0:
        step.status = 'ready'
    else:
        step.status = 'draft'  # Still has ungenerated recipients
    db.session.commit()

    return jsonify({
        'success': True,
        'generated': generated,
        'failed': failed,
        'remaining': remaining,
    })


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/approve', methods=['POST'])
def approve_step_recipients(id, step_id):
    """Approve step recipients for sending."""
    Campaign.query.get_or_404(id)
    CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    data = request.get_json(silent=True) or {}
    sr_ids = data.get('recipient_ids', [])

    if sr_ids:
        StepRecipient.query.filter(
            StepRecipient.id.in_(sr_ids),
            StepRecipient.step_id == step_id,
        ).update({'approved': True, 'status': 'approved'}, synchronize_session=False)
    else:
        # Approve all ready recipients
        StepRecipient.query.filter_by(
            step_id=step_id, status='ready'
        ).update({'approved': True, 'status': 'approved'}, synchronize_session=False)

    db.session.commit()
    return jsonify({'success': True})


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/recipients/<int:sr_id>', methods=['PUT'])
def update_step_recipient(id, step_id, sr_id):
    """Edit a step recipient's generated content."""
    Campaign.query.get_or_404(id)
    CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()
    sr = StepRecipient.query.filter_by(id=sr_id, step_id=step_id).first_or_404()

    data = request.get_json()

    if 'personalized_subject' in data:
        sr.personalized_subject = data['personalized_subject']
    if 'personalized_body' in data:
        sr.personalized_body = data['personalized_body']
    if 'approved' in data:
        sr.approved = data['approved']
        if data['approved'] and sr.status == 'ready':
            sr.status = 'approved'

    db.session.commit()
    return jsonify(sr.to_dict())


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/recipients/<int:sr_id>/regenerate', methods=['POST'])
def regenerate_step_recipient(id, step_id, sr_id):
    """Regenerate content for a single step recipient."""
    campaign = Campaign.query.get_or_404(id)
    step = CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()
    sr = StepRecipient.query.filter_by(id=sr_id, step_id=step_id).first_or_404()

    recipient = Recipient.query.get_or_404(sr.recipient_id)

    api_key = Settings.get('anthropic_api_key')
    if not api_key:
        return jsonify({'error': 'Anthropic API key not configured'}), 400

    claude = ClaudeService(api_key)
    writing_style = _get_writing_style()
    learned_insights = _get_learned_insights()

    try:
        if step.step_type == 'ai_followup':
            conversation_history = _build_conversation_history(campaign.id, recipient.id, step.position)

            # Web research
            research_text = None
            if step.use_web_research:
                tavily_key = Settings.get('tavily_api_key')
                if tavily_key:
                    from app.services.web_search import WebSearchService
                    web_search = WebSearchService(tavily_key)
                    custom_fields = recipient.get_custom_fields()
                    research = web_search.research_company(
                        company=recipient.company or '',
                        industry=custom_fields.get('industry') or custom_fields.get('sector'),
                        custom_query=step.web_research_prompt,
                        recipient_name=recipient.name,
                    )
                    research_text = WebSearchService.format_for_prompt(research)
                    sr.web_research_results = json.dumps(research)

            original_subject = _get_original_subject(campaign.id, recipient.id)

            result = claude.generate_sequence_followup(
                step_number=step.position,
                original_subject=original_subject,
                conversation_history=conversation_history,
                contact_info={'name': recipient.name, 'company': recipient.company},
                ai_prompt=step.ai_prompt,
                campaign_context=campaign.campaign_context,
                web_research=research_text,
                writing_style=writing_style,
                learned_insights=learned_insights,
            )
            sr.personalized_subject = result.get('subject', f'Re: {original_subject}')
            sr.personalized_body = result.get('body', '')

        elif step.step_type == 'template' and step.template_id:
            template = Template.query.get(step.template_id)
            if not template:
                return jsonify({'error': 'Template not found'}), 400

            recipient_dict = {
                'name': recipient.name,
                'email': recipient.email,
                'company': recipient.company,
                'custom_fields': recipient.get_all_context()
            }
            result = claude.personalize_email(
                template_subject=template.subject,
                template_body=template.body,
                recipient=recipient_dict,
                custom_prompt=campaign.ai_prompt,
                writing_style=writing_style,
                campaign_context=campaign.campaign_context,
                learned_insights=learned_insights,
            )
            sr.personalized_subject = result.get('subject', template.subject)
            sr.personalized_body = result.get('body', template.body)

        sr.approved = False  # Reset approval after regeneration
        sr.status = 'ready'
        db.session.commit()

        return jsonify(sr.to_dict())

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@campaigns_bp.route('/<int:id>/steps/<int:step_id>/start', methods=['POST'])
def start_step(id, step_id):
    """Manually trigger sending for a step (for steps that don't auto-send)."""
    campaign = Campaign.query.get_or_404(id)
    step = CampaignStep.query.filter_by(id=step_id, campaign_id=id).first_or_404()

    if step.status == 'running':
        return jsonify({'error': 'Step is already running'}), 400

    # Get approved recipients with content
    approved_srs = StepRecipient.query.filter_by(
        step_id=step_id,
    ).filter(
        StepRecipient.approved == True,
        StepRecipient.status.in_(['ready', 'approved']),
        StepRecipient.personalized_body.isnot(None),
    ).all()

    if not approved_srs:
        return jsonify({'error': 'No approved recipients with content ready to send'}), 400

    # Verify Gmail account
    account_id = campaign.gmail_account_id
    if account_id:
        account = OAuthToken.get_by_id(account_id)
    else:
        account = OAuthToken.get_default_gmail()
    if not account:
        return jsonify({'error': 'No Gmail account connected'}), 400
    account_id = account.id

    from app.services.step_runner import StepRunner
    StepRunner.start(
        campaign.id, step.id,
        [sr.id for sr in approved_srs],
        campaign.delay_seconds, account_id,
    )

    # If campaign isn't already in sequence mode, set it
    if campaign.status not in ('running', 'sequence_active'):
        campaign.status = 'sequence_active'
        db.session.commit()

    return jsonify({'success': True, 'status': 'running', 'recipients': len(approved_srs)})


# ---- Step helper functions ----

def _populate_step_recipients(step):
    """Create StepRecipient rows for all recipients in the campaign."""
    recipients = Recipient.query.filter_by(campaign_id=step.campaign_id).all()
    for r in recipients:
        existing = StepRecipient.query.filter_by(step_id=step.id, recipient_id=r.id).first()
        if not existing:
            sr = StepRecipient(step_id=step.id, recipient_id=r.id)
            db.session.add(sr)
    step.total_recipients = len(recipients)
    db.session.commit()


def _build_conversation_history(campaign_id, recipient_id, up_to_position):
    """Build a list of all emails sent to a recipient in prior steps."""
    history = []

    prior_steps = (
        CampaignStep.query
        .filter_by(campaign_id=campaign_id)
        .filter(CampaignStep.position < up_to_position)
        .order_by(CampaignStep.position)
        .all()
    )

    for ps in prior_steps:
        sr = StepRecipient.query.filter_by(step_id=ps.id, recipient_id=recipient_id).first()
        if sr and sr.personalized_body:
            history.append({
                'subject': sr.personalized_subject or '',
                'body': sr.personalized_body or '',
                'sent_at': sr.sent_at.isoformat() if sr.sent_at else 'not yet sent',
            })

    # Fallback: check original Recipient model for step 1 content (backward compat)
    if not history:
        r = Recipient.query.get(recipient_id)
        if r and r.personalized_body:
            history.append({
                'subject': r.personalized_subject or '',
                'body': r.personalized_body or '',
                'sent_at': r.sent_at.isoformat() if hasattr(r, 'sent_at') and r.sent_at else 'unknown',
            })

    return history


def _get_original_subject(campaign_id, recipient_id):
    """Get the original email subject for thread continuity."""
    log = (
        EmailLog.query
        .filter_by(campaign_id=campaign_id, recipient_id=recipient_id)
        .order_by(EmailLog.created_at.asc())
        .first()
    )
    if log and log.subject:
        return log.subject

    # Fallback: step 1 content
    step1 = CampaignStep.query.filter_by(campaign_id=campaign_id, position=1).first()
    if step1:
        sr = StepRecipient.query.filter_by(step_id=step1.id, recipient_id=recipient_id).first()
        if sr and sr.personalized_subject:
            return sr.personalized_subject

    # Final fallback
    r = Recipient.query.get(recipient_id)
    if r and r.personalized_subject:
        return r.personalized_subject

    return 'Hello'
