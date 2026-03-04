"""
Deal Tracker routes — CRUD for tracking live deals through
the acquisition pipeline (or sales pipeline in other workspaces).
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.deal import Deal, DEAL_STAGES, DEAL_STAGE_LABELS, DEAL_STAGE_COLORS
from app.models.listing import Listing
from app.models.monitored_site import MonitoredSite
from datetime import datetime, date

deals_bp = Blueprint('deals', __name__)


@deals_bp.route('/', methods=['GET'])
def list_deals():
    """List deals with optional filtering, searching, and sorting."""
    query = Deal.query.filter_by(workspace_id=g.workspace_id)

    # Stage filter
    stage = request.args.get('stage')
    if stage:
        if ',' in stage:
            query = query.filter(Deal.stage.in_(stage.split(',')))
        else:
            query = query.filter_by(stage=stage)

    # Text search
    q = request.args.get('q', '').strip()
    if q:
        pattern = f'%{q}%'
        query = query.filter(db.or_(
            Deal.name.ilike(pattern),
            Deal.broker_name.ilike(pattern),
            Deal.source.ilike(pattern),
            Deal.location.ilike(pattern),
            Deal.category.ilike(pattern),
        ))

    # Sorting
    sort_by = request.args.get('sort', 'updated_at')
    order = request.args.get('order', 'desc')
    sort_col = getattr(Deal, sort_by, Deal.updated_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    deals = query.all()
    return jsonify({'deals': [d.to_dict() for d in deals]})


@deals_bp.route('/stats', methods=['GET'])
def get_stats():
    """Pipeline stats: counts per stage and total pipeline value."""
    ws_id = g.workspace_id
    total = Deal.query.filter_by(workspace_id=ws_id).count()

    by_stage = {}
    for stage in DEAL_STAGES:
        by_stage[stage] = Deal.query.filter_by(workspace_id=ws_id, stage=stage).count()

    active_stages = [s for s in DEAL_STAGES if s not in ('closed_won', 'closed_lost')]

    pipeline_value = db.session.query(db.func.sum(Deal.asking_price)).filter(
        Deal.workspace_id == ws_id,
        Deal.stage.in_(active_stages),
        Deal.asking_price.isnot(None),
    ).scalar() or 0

    offer_value = db.session.query(db.func.sum(Deal.offer_price)).filter(
        Deal.workspace_id == ws_id,
        Deal.stage.in_(active_stages),
        Deal.offer_price.isnot(None),
    ).scalar() or 0

    won_value = db.session.query(db.func.sum(Deal.asking_price)).filter(
        Deal.workspace_id == ws_id,
        Deal.stage == 'closed_won',
    ).scalar() or 0

    return jsonify({
        'total': total,
        'by_stage': by_stage,
        'pipeline_value': pipeline_value,
        'offer_value': offer_value,
        'won_value': won_value,
        'active_count': sum(by_stage.get(s, 0) for s in active_stages),
    })


@deals_bp.route('/stages', methods=['GET'])
def list_stages():
    """Return available deal stages for the frontend."""
    return jsonify([
        {'value': s, 'label': DEAL_STAGE_LABELS[s], 'color': DEAL_STAGE_COLORS[s]}
        for s in DEAL_STAGES
    ])


@deals_bp.route('/<int:deal_id>', methods=['GET'])
def get_deal(deal_id):
    """Get a single deal."""
    deal = Deal.query.get(deal_id)
    if not deal or deal.workspace_id != g.workspace_id:
        return jsonify({'error': 'Deal not found'}), 404
    return jsonify(deal.to_dict())


@deals_bp.route('/', methods=['POST'])
def create_deal():
    """Create a new deal manually."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Deal name is required'}), 400

    stage = data.get('stage', 'interested')
    if stage not in DEAL_STAGES:
        return jsonify({'error': f'Invalid stage. Must be one of: {", ".join(DEAL_STAGES)}'}), 400

    deal = Deal(
        workspace_id=g.workspace_id,
        name=name,
        stage=stage,
        listing_id=data.get('listing_id'),
        contact_id=data.get('contact_id'),
        asking_price=data.get('asking_price'),
        offer_price=data.get('offer_price'),
        revenue=data.get('revenue'),
        cash_flow=data.get('cash_flow'),
        sde=data.get('sde'),
        ebitda=data.get('ebitda'),
        broker_name=data.get('broker_name'),
        broker_email=data.get('broker_email'),
        broker_phone=data.get('broker_phone'),
        source=data.get('source'),
        url=data.get('url'),
        location=data.get('location'),
        category=data.get('category'),
        notes=data.get('notes'),
    )

    if data.get('expected_close_date'):
        try:
            deal.expected_close_date = date.fromisoformat(data['expected_close_date'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    db.session.add(deal)
    db.session.commit()
    return jsonify(deal.to_dict()), 201


@deals_bp.route('/<int:deal_id>', methods=['PUT'])
def update_deal(deal_id):
    """Update deal fields."""
    deal = Deal.query.get(deal_id)
    if not deal or deal.workspace_id != g.workspace_id:
        return jsonify({'error': 'Deal not found'}), 404

    data = request.get_json() or {}

    updatable = [
        'name', 'listing_id', 'contact_id', 'asking_price', 'offer_price',
        'revenue', 'cash_flow', 'sde', 'ebitda', 'broker_name',
        'broker_email', 'broker_phone', 'source', 'url', 'location',
        'category', 'notes',
    ]
    for field in updatable:
        if field in data:
            setattr(deal, field, data[field])

    # Handle stage change — update stage_changed_at
    if 'stage' in data and data['stage'] != deal.stage:
        if data['stage'] not in DEAL_STAGES:
            return jsonify({'error': 'Invalid stage'}), 400
        deal.stage = data['stage']
        deal.stage_changed_at = datetime.utcnow()

    # Handle expected_close_date
    if 'expected_close_date' in data:
        if data['expected_close_date']:
            try:
                deal.expected_close_date = date.fromisoformat(data['expected_close_date'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            deal.expected_close_date = None

    db.session.commit()
    return jsonify(deal.to_dict())


@deals_bp.route('/<int:deal_id>/stage', methods=['PUT'])
def update_stage(deal_id):
    """Quick action: update deal stage only."""
    deal = Deal.query.get(deal_id)
    if not deal or deal.workspace_id != g.workspace_id:
        return jsonify({'error': 'Deal not found'}), 404

    data = request.get_json() or {}
    new_stage = data.get('stage')
    if not new_stage or new_stage not in DEAL_STAGES:
        return jsonify({'error': 'Invalid stage'}), 400

    deal.stage = new_stage
    deal.stage_changed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(deal.to_dict())


@deals_bp.route('/from-listing/<int:listing_id>', methods=['POST'])
def create_from_listing(listing_id):
    """Create a deal from an existing listing, copying financial data."""
    listing = Listing.query.get(listing_id)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    # Verify workspace ownership through the monitored site
    site = MonitoredSite.query.get(listing.site_id)
    if not site or site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Listing not found'}), 404

    data = request.get_json() or {}

    deal = Deal(
        workspace_id=g.workspace_id,
        name=data.get('name') or listing.title or 'Untitled Deal',
        stage=data.get('stage', 'interested'),
        listing_id=listing.id,
        contact_id=data.get('contact_id'),
        asking_price=listing.price_numeric,
        revenue=listing.revenue,
        cash_flow=listing.cash_flow,
        sde=listing.sde,
        ebitda=listing.ebitda,
        source=data.get('source') or 'listing',
        url=listing.url,
        location=listing.location,
        category=listing.normalized_category or listing.category,
        notes=data.get('notes'),
        broker_name=data.get('broker_name'),
        broker_email=data.get('broker_email'),
        broker_phone=data.get('broker_phone'),
    )
    db.session.add(deal)
    db.session.commit()
    return jsonify(deal.to_dict()), 201


@deals_bp.route('/<int:deal_id>', methods=['DELETE'])
def delete_deal(deal_id):
    """Delete a deal."""
    deal = Deal.query.get(deal_id)
    if not deal or deal.workspace_id != g.workspace_id:
        return jsonify({'error': 'Deal not found'}), 404
    db.session.delete(deal)
    db.session.commit()
    return jsonify({'success': True})
