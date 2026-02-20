"""
Signal routes — manage intent signals and signal sources.
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.signal import Signal
from app.models.signal_source import SignalSource
from app.models.contact import Contact
import json
import threading

signals_bp = Blueprint('signals', __name__)


@signals_bp.route('', methods=['GET'])
def list_signals():
    """List signals for the current workspace."""
    query = Signal.query.filter_by(workspace_id=g.workspace_id)

    # Filters
    source_type = request.args.get('source_type')
    if source_type:
        query = query.filter_by(source_type=source_type)

    signal_type = request.args.get('signal_type')
    if signal_type:
        query = query.filter_by(signal_type=signal_type)

    contact_id = request.args.get('contact_id', type=int)
    if contact_id:
        query = query.filter_by(contact_id=contact_id)

    min_intent = request.args.get('min_intent', type=float)
    if min_intent is not None:
        query = query.filter(Signal.intent_score >= min_intent)

    actioned = request.args.get('actioned')
    if actioned == 'true':
        query = query.filter_by(actioned=True)
    elif actioned == 'false':
        query = query.filter_by(actioned=False)

    dismissed = request.args.get('dismissed')
    if dismissed is None:
        query = query.filter_by(dismissed=False)
    elif dismissed == 'true':
        query = query.filter_by(dismissed=True)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    signals = query.order_by(Signal.detected_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'signals': [s.to_dict() for s in signals.items],
        'total': signals.total,
        'page': signals.page,
        'pages': signals.pages,
    })


@signals_bp.route('/<int:signal_id>/create-outreach', methods=['POST'])
def create_outreach(signal_id):
    """Generate outreach email from a signal."""
    signal = Signal.query.filter_by(
        id=signal_id, workspace_id=g.workspace_id
    ).first_or_404()

    contact = Contact.query.get(signal.contact_id) if signal.contact_id else None
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    data = request.json or {}
    campaign_id = data.get('campaign_id')

    try:
        from app.models.settings import Settings, WorkspaceSettings
        from app.services.claude_service import ClaudeService

        api_key = Settings.get('anthropic_api_key')
        if not api_key:
            return jsonify({'error': 'No API key configured'}), 400

        claude = ClaudeService(api_key)

        trigger_context = {
            'type': signal.signal_type,
            'details': signal.get_raw_data(),
            'severity': signal.severity,
            'source': signal.source_type,
            'title': signal.title,
            'summary': signal.summary,
        }

        writing_style = None
        raw_style = WorkspaceSettings.get(g.workspace_id, 'writing_style')
        if raw_style:
            try:
                writing_style = json.loads(raw_style)
            except Exception:
                pass

        result = claude.generate_trigger_email(
            trigger_type=signal.signal_type,
            trigger_context=trigger_context,
            contact_info={
                'name': contact.name or '',
                'email': contact.email,
                'company': contact.company or '',
                'website': contact.website or '',
            },
            writing_style=writing_style,
        )

        signal.outreach_subject = result.get('subject', '')
        signal.outreach_body = result.get('body', '')
        signal.actioned = True
        if campaign_id:
            signal.campaign_id = campaign_id

        db.session.commit()

        return jsonify({
            'success': True,
            'subject': signal.outreach_subject,
            'body': signal.outreach_body,
            'signal': signal.to_dict(),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@signals_bp.route('/<int:signal_id>/dismiss', methods=['POST'])
def dismiss_signal(signal_id):
    """Dismiss a signal."""
    signal = Signal.query.filter_by(
        id=signal_id, workspace_id=g.workspace_id
    ).first_or_404()

    signal.dismissed = True
    db.session.commit()
    return jsonify(signal.to_dict())


@signals_bp.route('/stats', methods=['GET'])
def signal_stats():
    """Get signal summary stats."""
    from sqlalchemy import func

    ws_id = g.workspace_id

    # Count by source type
    source_counts = db.session.query(
        Signal.source_type, func.count(Signal.id)
    ).filter(
        Signal.workspace_id == ws_id,
        Signal.dismissed == False,
    ).group_by(Signal.source_type).all()

    # Count by severity
    severity_counts = db.session.query(
        Signal.severity, func.count(Signal.id)
    ).filter(
        Signal.workspace_id == ws_id,
        Signal.dismissed == False,
    ).group_by(Signal.severity).all()

    total = sum(c for _, c in source_counts)
    actioned = Signal.query.filter_by(
        workspace_id=ws_id, actioned=True, dismissed=False
    ).count()

    # Average intent score
    avg_intent = db.session.query(func.avg(Signal.intent_score)).filter(
        Signal.workspace_id == ws_id,
        Signal.dismissed == False,
        Signal.intent_score.isnot(None),
    ).scalar()

    return jsonify({
        'total': total,
        'actioned': actioned,
        'pending': total - actioned,
        'avg_intent_score': round(avg_intent, 3) if avg_intent else 0,
        'by_source': {s: c for s, c in source_counts},
        'by_severity': {s: c for s, c in severity_counts},
    })


# ─── Signal Sources ──────────────────────────────────────────────

@signals_bp.route('/sources', methods=['GET'])
def list_sources():
    """List signal sources for the current workspace."""
    sources = SignalSource.query.filter_by(
        workspace_id=g.workspace_id
    ).order_by(SignalSource.created_at.desc()).all()

    return jsonify({
        'sources': [s.to_dict() for s in sources],
    })


@signals_bp.route('/sources', methods=['POST'])
def create_source():
    """Create a new signal source."""
    data = request.json or {}

    source_type = data.get('source_type')
    if not source_type:
        return jsonify({'error': 'source_type is required'}), 400

    source = SignalSource(
        workspace_id=g.workspace_id,
        source_type=source_type,
        name=data.get('name', source_type.replace('_', ' ').title()),
        config=json.dumps(data.get('config', {})),
        is_active=data.get('is_active', True),
        check_interval_hours=data.get('check_interval_hours', 24),
    )
    db.session.add(source)
    db.session.commit()

    return jsonify(source.to_dict()), 201


@signals_bp.route('/sources/<int:source_id>', methods=['PUT'])
def update_source(source_id):
    """Update a signal source."""
    source = SignalSource.query.filter_by(
        id=source_id, workspace_id=g.workspace_id
    ).first_or_404()

    data = request.json or {}

    if 'name' in data:
        source.name = data['name']
    if 'config' in data:
        source.config = json.dumps(data['config'])
    if 'is_active' in data:
        source.is_active = data['is_active']
    if 'check_interval_hours' in data:
        source.check_interval_hours = data['check_interval_hours']

    db.session.commit()
    return jsonify(source.to_dict())


@signals_bp.route('/collect-now', methods=['POST'])
def collect_now():
    """Trigger immediate signal collection for workspace."""
    from flask import current_app
    from app.services.signal_engine import SignalEngine

    app = current_app._get_current_object()
    ws_id = g.workspace_id

    def run_collection():
        with app.app_context():
            try:
                count = SignalEngine.collect_for_workspace(ws_id)
                app.logger.info(f'Manual signal collection found {count} new signals')
            except Exception as e:
                app.logger.error(f'Manual signal collection error: {e}')

    thread = threading.Thread(target=run_collection, daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': 'Signal collection started in background'})
