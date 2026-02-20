"""
Opportunities routes — aggregated opportunity feed that ranks contacts
by their combined signal strength and relevance.
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.signal import Signal
from app.models.contact import Contact
from sqlalchemy import func

opportunities_bp = Blueprint('opportunities', __name__)


@opportunities_bp.route('/feed', methods=['GET'])
def opportunity_feed():
    """
    Get ranked opportunity feed: contacts with highest-intent signals.
    Groups signals by contact, ranks by max(intent_score * relevance_score).
    """
    ws_id = g.workspace_id

    # Filters
    min_score = request.args.get('min_score', 0.0, type=float)
    source_type = request.args.get('source_type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Get contacts with active signals, ranked by max intent
    # Subquery: max intent score per contact
    signal_query = db.session.query(
        Signal.contact_id,
        func.max(Signal.intent_score).label('max_intent'),
        func.max(Signal.relevance_score).label('max_relevance'),
        func.count(Signal.id).label('signal_count'),
        func.max(Signal.detected_at).label('latest_signal'),
    ).filter(
        Signal.workspace_id == ws_id,
        Signal.dismissed == False,
        Signal.contact_id.isnot(None),
    )

    if source_type:
        signal_query = signal_query.filter(Signal.source_type == source_type)

    signal_agg = signal_query.group_by(Signal.contact_id).subquery()

    # Join with contacts and rank
    results = db.session.query(
        Contact,
        signal_agg.c.max_intent,
        signal_agg.c.max_relevance,
        signal_agg.c.signal_count,
        signal_agg.c.latest_signal,
    ).join(
        signal_agg, Contact.id == signal_agg.c.contact_id
    ).filter(
        Contact.workspace_id == ws_id,
    )

    # Score filter
    if min_score > 0:
        results = results.filter(signal_agg.c.max_intent >= min_score)

    # Order by combined score (intent * relevance), falling back to intent alone
    results = results.order_by(
        (func.coalesce(signal_agg.c.max_intent, 0) *
         func.coalesce(signal_agg.c.max_relevance, 0.5)).desc(),
        signal_agg.c.latest_signal.desc(),
    )

    # Paginate
    total = results.count()
    items = results.offset((page - 1) * per_page).limit(per_page).all()

    # Build response with top signals per contact
    opportunities = []
    for contact, max_intent, max_relevance, signal_count, latest_signal in items:
        # Get top 3 signals for this contact
        top_signals = Signal.query.filter(
            Signal.workspace_id == ws_id,
            Signal.contact_id == contact.id,
            Signal.dismissed == False,
        ).order_by(
            Signal.intent_score.desc()
        ).limit(3).all()

        combined_score = (max_intent or 0) * (max_relevance or 0.5)

        opportunities.append({
            'contact': {
                'id': contact.id,
                'name': contact.name,
                'email': contact.email,
                'company': contact.company,
                'website': contact.website,
                'status': contact.status,
                'business_category': contact.business_category,
            },
            'max_intent_score': round(max_intent, 3) if max_intent else 0,
            'max_relevance_score': round(max_relevance, 3) if max_relevance else 0,
            'combined_score': round(combined_score, 3),
            'signal_count': signal_count,
            'latest_signal_at': latest_signal.isoformat() if latest_signal else None,
            'top_signals': [s.to_dict() for s in top_signals],
        })

    return jsonify({
        'opportunities': opportunities,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page if per_page > 0 else 0,
    })
