"""
Cowork Data API — read-only endpoints that reshape existing platform data
for Cowork plugin consumption. Mutations go through existing endpoints.
Also includes webhook subscription management.
"""
import json
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g

from app import db
from app.models.acquisition_thesis import AcquisitionThesis
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.reply_message import ReplyMessage
from app.models.signal import Signal
from app.models.webhook_subscription import WebhookSubscription, WEBHOOK_EVENTS

cowork_bp = Blueprint('cowork', __name__)


# ---------- Data Endpoints ----------


@cowork_bp.route('/targets', methods=['GET'])
def get_targets() -> tuple:
    """Get ranked target list with thesis context.

    Query params:
        thesis_id: Filter by thesis (required for scoring)
        min_score: Minimum thesis fit score (default 0)
        status: Filter by lead status (comma-separated)
        limit: Max results (default 50, max 200)
    """
    thesis_id = request.args.get('thesis_id', type=int)
    min_score = request.args.get('min_score', 0, type=int)
    status_filter = request.args.get('status')
    limit = min(request.args.get('limit', 50, type=int), 200)

    query = Lead.query.filter(
        Lead.workspace_id == g.workspace_id,
        Lead.status.notin_(['rejected']),
    )

    if status_filter:
        statuses = [s.strip() for s in status_filter.split(',')]
        query = query.filter(Lead.status.in_(statuses))

    if thesis_id:
        from app.services.thesis_scorer import ThesisScorer
        ranked = ThesisScorer.rank_leads(
            g.workspace_id, thesis_id, limit=limit, min_score=min_score,
        )
        return jsonify({
            'thesis_id': thesis_id,
            'targets': ranked,
            'count': len(ranked),
        })

    # Without thesis, return leads sorted by score
    leads = query.order_by(Lead.score.desc().nullslast()).limit(limit).all()
    return jsonify({
        'targets': [l.to_dict() for l in leads],
        'count': len(leads),
    })


@cowork_bp.route('/deals', methods=['GET'])
def get_deals() -> tuple:
    """Get active deals with financial data.

    Query params:
        stage: Filter by stage (comma-separated)
        limit: Max results (default 50)
    """
    query = Deal.query.filter_by(workspace_id=g.workspace_id)

    stage_filter = request.args.get('stage')
    if stage_filter:
        stages = [s.strip() for s in stage_filter.split(',')]
        query = query.filter(Deal.stage.in_(stages))

    limit = min(request.args.get('limit', 50, type=int), 200)
    deals = query.order_by(Deal.updated_at.desc()).limit(limit).all()
    return jsonify({
        'deals': [d.to_dict() for d in deals],
        'count': len(deals),
    })


@cowork_bp.route('/replies', methods=['GET'])
def get_replies() -> tuple:
    """Get recent replies with sentiment and contact context.

    Query params:
        since: ISO date (default 7 days ago)
        sentiment: Filter by sentiment (comma-separated)
        limit: Max results (default 50)
    """
    since_str = request.args.get('since')
    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    else:
        since = datetime.utcnow() - timedelta(days=7)

    query = ReplyMessage.query.filter(
        ReplyMessage.workspace_id == g.workspace_id,
        ReplyMessage.received_at >= since,
    )

    sentiment_filter = request.args.get('sentiment')
    if sentiment_filter:
        sentiments = [s.strip() for s in sentiment_filter.split(',')]
        query = query.filter(ReplyMessage.sentiment.in_(sentiments))

    limit = min(request.args.get('limit', 50, type=int), 200)
    replies = query.order_by(ReplyMessage.received_at.desc()).limit(limit).all()
    return jsonify({
        'replies': [r.to_dict() for r in replies],
        'count': len(replies),
    })


@cowork_bp.route('/signals', methods=['GET'])
def get_signals() -> tuple:
    """Get high-relevance signals for deal evaluation.

    Query params:
        since: ISO date (default 7 days ago)
        min_relevance: Minimum relevance score (default 0)
        limit: Max results (default 50)
    """
    since_str = request.args.get('since')
    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    else:
        since = datetime.utcnow() - timedelta(days=7)

    min_relevance = request.args.get('min_relevance', 0, type=int)
    limit = min(request.args.get('limit', 50, type=int), 200)

    query = Signal.query.filter(
        Signal.workspace_id == g.workspace_id,
        Signal.detected_at >= since,
    )

    if min_relevance > 0:
        query = query.filter(Signal.relevance_score >= min_relevance)

    signals = query.order_by(Signal.relevance_score.desc()).limit(limit).all()
    return jsonify({
        'signals': [s.to_dict() for s in signals],
        'count': len(signals),
    })


@cowork_bp.route('/report/weekly', methods=['GET'])
def get_weekly_report() -> tuple:
    """Alias to weekly deal flow report."""
    from app.services.report_service import ReportService
    report = ReportService.generate_weekly_report(workspace_id=g.workspace_id)
    return jsonify(report)


@cowork_bp.route('/report/daily-brief', methods=['GET'])
def get_daily_brief() -> tuple:
    """Enhanced daily brief with thesis context.

    Returns thesis-level summary with high-score target counts
    alongside basic pipeline and outreach metrics.
    """
    ws_id = g.workspace_id

    # Thesis summary
    theses = AcquisitionThesis.query.filter_by(
        workspace_id=ws_id,
        status='active',
    ).all()

    thesis_summary = []
    for thesis in theses:
        high_score_leads = Lead.query.filter(
            Lead.workspace_id == ws_id,
            Lead.thesis_fit_score >= 70,
            Lead.status.notin_(['rejected']),
        ).count()

        total_leads = Lead.query.filter(
            Lead.workspace_id == ws_id,
            Lead.status.notin_(['rejected']),
        ).count()

        thesis_summary.append({
            'thesis_id': thesis.id,
            'thesis_name': thesis.name,
            'vertical': thesis.vertical,
            'high_score_targets': high_score_leads,
            'total_targets': total_leads,
        })

    # Active deal count
    active_deals = Deal.query.filter(
        Deal.workspace_id == ws_id,
        Deal.stage.notin_(['closed_won', 'closed_lost']),
    ).count()

    # Recent replies (last 24h)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_replies = ReplyMessage.query.filter(
        ReplyMessage.workspace_id == ws_id,
        ReplyMessage.received_at >= yesterday,
    ).count()

    return jsonify({
        'thesis_summary': thesis_summary,
        'active_deals': active_deals,
        'recent_replies_24h': recent_replies,
        'generated_at': datetime.utcnow().isoformat(),
    })


# ---------- Webhook Management ----------


@cowork_bp.route('/webhooks', methods=['GET'])
def list_webhooks() -> tuple:
    """List webhook subscriptions."""
    subs = WebhookSubscription.query.filter_by(
        workspace_id=g.workspace_id,
    ).all()
    return jsonify({
        'webhooks': [s.to_dict() for s in subs],
        'available_events': WEBHOOK_EVENTS,
    })


@cowork_bp.route('/webhooks', methods=['POST'])
def create_webhook() -> tuple:
    """Create a webhook subscription."""
    data = request.get_json() or {}

    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'Webhook URL is required'}), 400
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URL must start with http:// or https://'}), 400

    events = data.get('events', [])
    if not events:
        return jsonify({'error': 'At least one event type is required'}), 400

    invalid_events = [e for e in events if e not in WEBHOOK_EVENTS]
    if invalid_events:
        return jsonify({'error': f'Invalid events: {", ".join(invalid_events)}'}), 400

    sub = WebhookSubscription(
        workspace_id=g.workspace_id,
        url=url,
        secret=data.get('secret'),
        is_active=data.get('is_active', True),
    )
    sub.set_events(events)

    db.session.add(sub)
    db.session.commit()
    return jsonify(sub.to_dict()), 201


@cowork_bp.route('/webhooks/<int:webhook_id>', methods=['PUT'])
def update_webhook(webhook_id: int) -> tuple:
    """Update a webhook subscription."""
    sub = WebhookSubscription.query.filter_by(
        id=webhook_id, workspace_id=g.workspace_id
    ).first()
    if not sub:
        return jsonify({'error': 'Webhook not found'}), 404

    data = request.get_json() or {}

    if 'url' in data:
        url = (data['url'] or '').strip()
        if not url.startswith(('http://', 'https://')):
            return jsonify({'error': 'URL must start with http:// or https://'}), 400
        sub.url = url

    if 'events' in data:
        invalid = [e for e in data['events'] if e not in WEBHOOK_EVENTS]
        if invalid:
            return jsonify({'error': f'Invalid events: {", ".join(invalid)}'}), 400
        sub.set_events(data['events'])

    if 'secret' in data:
        sub.secret = data['secret']
    if 'is_active' in data:
        sub.is_active = data['is_active']

    db.session.commit()
    return jsonify(sub.to_dict())


@cowork_bp.route('/webhooks/<int:webhook_id>', methods=['DELETE'])
def delete_webhook(webhook_id: int) -> tuple:
    """Delete a webhook subscription."""
    sub = WebhookSubscription.query.filter_by(
        id=webhook_id, workspace_id=g.workspace_id
    ).first()
    if not sub:
        return jsonify({'error': 'Webhook not found'}), 404
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'success': True})
