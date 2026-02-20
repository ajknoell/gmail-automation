"""
Trigger routes — manage website triggers and trigger-based outreach.
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.website_trigger import WebsiteTrigger
from app.models.contact import Contact
import json
import threading

triggers_bp = Blueprint('triggers', __name__)


@triggers_bp.route('', methods=['GET'])
def list_triggers():
    """List triggers for the current workspace."""
    query = WebsiteTrigger.query.filter_by(workspace_id=g.workspace_id)

    # Filters
    trigger_type = request.args.get('type')
    if trigger_type:
        query = query.filter_by(trigger_type=trigger_type)

    actioned = request.args.get('actioned')
    if actioned == 'true':
        query = query.filter_by(actioned=True)
    elif actioned == 'false':
        query = query.filter_by(actioned=False)

    dismissed = request.args.get('dismissed')
    if dismissed is None:
        # Default: hide dismissed triggers
        query = query.filter_by(dismissed=False)
    elif dismissed == 'true':
        query = query.filter_by(dismissed=True)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    triggers = query.order_by(WebsiteTrigger.detected_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'triggers': [t.to_dict() for t in triggers.items],
        'total': triggers.total,
        'page': triggers.page,
        'pages': triggers.pages,
    })


@triggers_bp.route('/<int:trigger_id>/create-outreach', methods=['POST'])
def create_outreach(trigger_id):
    """Generate outreach email from a trigger."""
    trigger = WebsiteTrigger.query.filter_by(
        id=trigger_id, workspace_id=g.workspace_id
    ).first_or_404()

    contact = Contact.query.get(trigger.contact_id)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    data = request.json or {}
    campaign_id = data.get('campaign_id')

    # Generate trigger-specific email via Claude
    try:
        from app.models.settings import Settings, WorkspaceSettings
        from app.services.claude_service import ClaudeService

        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return jsonify({'error': 'No API key configured'}), 400

        claude = ClaudeService(api_key)

        # Build trigger context
        trigger_context = {
            'type': trigger.trigger_type,
            'details': trigger.get_current_value(),
            'severity': trigger.severity,
        }

        # Get writing style
        writing_style = None
        raw_style = WorkspaceSettings.get(g.workspace_id, 'writing_style')
        if raw_style:
            try:
                writing_style = json.loads(raw_style)
            except Exception:
                pass

        result = claude.generate_trigger_email(
            trigger_type=trigger.trigger_type,
            trigger_context=trigger_context,
            contact_info={
                'name': contact.name or '',
                'email': contact.email,
                'company': contact.company or '',
                'website': contact.website or '',
            },
            writing_style=writing_style,
        )

        trigger.outreach_subject = result.get('subject', '')
        trigger.outreach_body = result.get('body', '')
        trigger.actioned = True
        if campaign_id:
            trigger.campaign_id = campaign_id

        db.session.commit()

        return jsonify({
            'success': True,
            'subject': trigger.outreach_subject,
            'body': trigger.outreach_body,
            'trigger': trigger.to_dict(),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@triggers_bp.route('/<int:trigger_id>/dismiss', methods=['PUT'])
def dismiss_trigger(trigger_id):
    """Mark a trigger as dismissed."""
    trigger = WebsiteTrigger.query.filter_by(
        id=trigger_id, workspace_id=g.workspace_id
    ).first_or_404()

    trigger.dismissed = True
    db.session.commit()
    return jsonify(trigger.to_dict())


@triggers_bp.route('/stats', methods=['GET'])
def trigger_stats():
    """Get trigger summary stats."""
    from sqlalchemy import func

    ws_id = g.workspace_id

    # Count by type
    type_counts = db.session.query(
        WebsiteTrigger.trigger_type, func.count(WebsiteTrigger.id)
    ).filter(
        WebsiteTrigger.workspace_id == ws_id,
        WebsiteTrigger.dismissed == False,
    ).group_by(WebsiteTrigger.trigger_type).all()

    # Count by severity
    severity_counts = db.session.query(
        WebsiteTrigger.severity, func.count(WebsiteTrigger.id)
    ).filter(
        WebsiteTrigger.workspace_id == ws_id,
        WebsiteTrigger.dismissed == False,
    ).group_by(WebsiteTrigger.severity).all()

    total = sum(c for _, c in type_counts)
    actioned = WebsiteTrigger.query.filter_by(
        workspace_id=ws_id, actioned=True, dismissed=False
    ).count()

    return jsonify({
        'total': total,
        'actioned': actioned,
        'pending': total - actioned,
        'by_type': {t: c for t, c in type_counts},
        'by_severity': {s: c for s, c in severity_counts},
    })


@triggers_bp.route('/config', methods=['GET'])
def get_trigger_config():
    """Get trigger monitoring config for workspace."""
    from app.models.settings import WorkspaceSettings

    raw = WorkspaceSettings.get(g.workspace_id, 'trigger_monitor_config')
    config = {
        'enabled': True,
        'check_interval_hours': 168,
        'check_ssl': True,
        'check_downtime': True,
        'check_content_change': True,
        'check_copyright': True,
    }
    if raw:
        try:
            config.update(json.loads(raw))
        except Exception:
            pass

    return jsonify(config)


@triggers_bp.route('/config', methods=['PUT'])
def update_trigger_config():
    """Update trigger monitoring config."""
    from app.models.settings import WorkspaceSettings

    data = request.json or {}
    WorkspaceSettings.set(g.workspace_id, 'trigger_monitor_config', json.dumps(data))
    db.session.commit()
    return jsonify(data)


@triggers_bp.route('/check-now', methods=['POST'])
def check_now():
    """Trigger an immediate check for all contacts in workspace."""
    from flask import current_app
    from app.services.trigger_monitor import TriggerMonitor

    app = current_app._get_current_object()
    ws_id = g.workspace_id

    def run_check():
        with app.app_context():
            try:
                contacts = Contact.query.filter(
                    Contact.workspace_id == ws_id,
                    Contact.website.isnot(None),
                    Contact.website != '',
                ).limit(50).all()

                count = 0
                for contact in contacts:
                    triggers = TriggerMonitor.check_contact(contact, ws_id)
                    for t in triggers:
                        db.session.add(t)
                        count += 1
                db.session.commit()
                app.logger.info(f'Manual trigger check found {count} new triggers')
            except Exception as e:
                app.logger.error(f'Manual trigger check error: {e}')

    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': 'Trigger check started in background'})
