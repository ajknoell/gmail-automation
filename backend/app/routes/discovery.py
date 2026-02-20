"""
Discovery routes — manage search criteria and discovered prospects.
"""
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.discovery_criteria import DiscoveryCriteria
from app.models.contact import Contact
from app.models.recipient import Recipient
import threading

discovery_bp = Blueprint('discovery', __name__)


@discovery_bp.route('/criteria', methods=['GET'])
def list_criteria():
    """List all discovery criteria for the current workspace."""
    criteria = DiscoveryCriteria.query.filter_by(
        workspace_id=g.workspace_id
    ).order_by(DiscoveryCriteria.created_at.desc()).all()
    return jsonify([c.to_dict() for c in criteria])


@discovery_bp.route('/criteria', methods=['POST'])
def create_criteria():
    """Create new discovery criteria."""
    data = request.json or {}

    criteria = DiscoveryCriteria(
        workspace_id=g.workspace_id,
        name=data.get('name', 'New Search'),
    )
    criteria.set_search_queries(data.get('search_queries', []))
    criteria.set_zip_codes(data.get('zip_codes', []))
    criteria.radius_miles = data.get('radius_miles', 10)
    criteria.min_rating = data.get('min_rating', 0.0)
    criteria.max_results_per_query = data.get('max_results_per_query', 20)
    criteria.exclude_chains = data.get('exclude_chains', False)
    criteria.is_active = data.get('is_active', True)
    criteria.scan_interval_hours = data.get('scan_interval_hours', 168)

    db.session.add(criteria)
    db.session.commit()

    return jsonify(criteria.to_dict()), 201


@discovery_bp.route('/criteria/<int:criteria_id>', methods=['PUT'])
def update_criteria(criteria_id):
    """Update existing discovery criteria."""
    criteria = DiscoveryCriteria.query.filter_by(
        id=criteria_id, workspace_id=g.workspace_id
    ).first_or_404()

    data = request.json or {}

    if 'name' in data:
        criteria.name = data['name']
    if 'search_queries' in data:
        criteria.set_search_queries(data['search_queries'])
    if 'zip_codes' in data:
        criteria.set_zip_codes(data['zip_codes'])
    if 'radius_miles' in data:
        criteria.radius_miles = data['radius_miles']
    if 'min_rating' in data:
        criteria.min_rating = data['min_rating']
    if 'max_results_per_query' in data:
        criteria.max_results_per_query = data['max_results_per_query']
    if 'exclude_chains' in data:
        criteria.exclude_chains = data['exclude_chains']
    if 'is_active' in data:
        criteria.is_active = data['is_active']
    if 'scan_interval_hours' in data:
        criteria.scan_interval_hours = data['scan_interval_hours']

    db.session.commit()
    return jsonify(criteria.to_dict())


@discovery_bp.route('/criteria/<int:criteria_id>', methods=['DELETE'])
def delete_criteria(criteria_id):
    """Delete discovery criteria."""
    criteria = DiscoveryCriteria.query.filter_by(
        id=criteria_id, workspace_id=g.workspace_id
    ).first_or_404()

    db.session.delete(criteria)
    db.session.commit()
    return jsonify({'success': True})


@discovery_bp.route('/scan-now', methods=['POST'])
def scan_now():
    """Trigger an immediate discovery scan."""
    from flask import current_app
    from app.services.prospect_discovery import ProspectDiscovery

    data = request.json or {}
    criteria_id = data.get('criteria_id')

    if criteria_id:
        criteria = DiscoveryCriteria.query.filter_by(
            id=criteria_id, workspace_id=g.workspace_id
        ).first_or_404()
        criteria_list = [criteria]
    else:
        criteria_list = DiscoveryCriteria.query.filter_by(
            workspace_id=g.workspace_id, is_active=True
        ).all()

    if not criteria_list:
        return jsonify({'error': 'No active criteria found'}), 400

    # Run in background thread
    app = current_app._get_current_object()
    ws_id = g.workspace_id

    def run_scan():
        with app.app_context():
            for c in criteria_list:
                try:
                    ProspectDiscovery.run_discovery(c, ws_id)
                except Exception as e:
                    app.logger.error(f'Discovery scan error: {e}')

    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Scanning {len(criteria_list)} criteria in background',
    })


@discovery_bp.route('/prospects', methods=['GET'])
def list_prospects():
    """List discovered contacts (status='discovered')."""
    query = Contact.query.filter_by(
        workspace_id=g.workspace_id,
        status='discovered',
    )

    # Filters
    category = request.args.get('category')
    if category:
        query = query.filter(Contact.business_category.ilike(f'%{category}%'))

    min_rating = request.args.get('min_rating', type=float)
    if min_rating:
        query = query.filter(Contact.google_rating >= min_rating)

    qualified = request.args.get('qualified')
    if qualified == 'true':
        query = query.filter(Contact.qualified == True)
    elif qualified == 'false':
        query = query.filter(Contact.qualified == False)

    criteria_id = request.args.get('criteria_id', type=int)
    if criteria_id:
        query = query.filter(Contact.discovery_criteria_id == criteria_id)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    contacts = query.order_by(Contact.discovered_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'prospects': [c.to_dict() for c in contacts.items],
        'total': contacts.total,
        'page': contacts.page,
        'pages': contacts.pages,
    })


@discovery_bp.route('/prospects/<int:contact_id>/qualify', methods=['POST'])
def qualify_prospect(contact_id):
    """Mark a prospect as qualified or unqualified."""
    contact = Contact.query.filter_by(
        id=contact_id, workspace_id=g.workspace_id
    ).first_or_404()

    data = request.json or {}
    contact.qualified = data.get('qualified', True)
    contact.qualification_reason = data.get('reason', '')
    db.session.commit()

    return jsonify(contact.to_dict())


@discovery_bp.route('/prospects/<int:contact_id>/add-to-campaign', methods=['POST'])
def add_to_campaign(contact_id):
    """Move a prospect to 'new' status and optionally add as campaign recipient."""
    contact = Contact.query.filter_by(
        id=contact_id, workspace_id=g.workspace_id
    ).first_or_404()

    data = request.json or {}
    campaign_id = data.get('campaign_id')

    # Advance status
    contact.status = 'new'
    contact.qualified = True

    # Add to campaign if specified
    if campaign_id:
        from app.models.campaign import Campaign
        campaign = Campaign.query.get(campaign_id)
        if campaign:
            # Check for duplicate
            existing = Recipient.query.filter_by(
                campaign_id=campaign_id, email=contact.email
            ).first()
            if not existing:
                recipient = Recipient(
                    campaign_id=campaign_id,
                    email=contact.email,
                    name=contact.name,
                    company=contact.company,
                )
                db.session.add(recipient)
                campaign.total_recipients = (campaign.total_recipients or 0) + 1

    db.session.commit()
    return jsonify(contact.to_dict())


@discovery_bp.route('/prospects/bulk-add', methods=['POST'])
def bulk_add_to_campaign():
    """Bulk add multiple prospects to a campaign."""
    data = request.json or {}
    contact_ids = data.get('contact_ids', [])
    campaign_id = data.get('campaign_id')

    if not contact_ids:
        return jsonify({'error': 'No contacts specified'}), 400

    added = 0
    for cid in contact_ids:
        contact = Contact.query.filter_by(
            id=cid, workspace_id=g.workspace_id
        ).first()
        if not contact:
            continue

        contact.status = 'new'
        contact.qualified = True

        if campaign_id:
            existing = Recipient.query.filter_by(
                campaign_id=campaign_id, email=contact.email
            ).first()
            if not existing:
                recipient = Recipient(
                    campaign_id=campaign_id,
                    email=contact.email,
                    name=contact.name,
                    company=contact.company,
                )
                db.session.add(recipient)
                added += 1

    if campaign_id:
        from app.models.campaign import Campaign
        campaign = Campaign.query.get(campaign_id)
        if campaign:
            campaign.total_recipients = (campaign.total_recipients or 0) + added

    db.session.commit()
    return jsonify({'success': True, 'added': added, 'total': len(contact_ids)})


@discovery_bp.route('/prospects/<int:contact_id>', methods=['DELETE'])
def dismiss_prospect(contact_id):
    """Dismiss (delete) a discovered prospect."""
    contact = Contact.query.filter_by(
        id=contact_id, workspace_id=g.workspace_id, status='discovered'
    ).first_or_404()

    db.session.delete(contact)
    db.session.commit()
    return jsonify({'success': True})


@discovery_bp.route('/stats', methods=['GET'])
def discovery_stats():
    """Get discovery summary stats."""
    from sqlalchemy import func

    ws_id = g.workspace_id

    total = Contact.query.filter_by(workspace_id=ws_id, status='discovered').count()
    qualified = Contact.query.filter_by(workspace_id=ws_id, status='discovered', qualified=True).count()
    unqualified = Contact.query.filter_by(workspace_id=ws_id, status='discovered', qualified=False).count()

    # Category breakdown
    categories = db.session.query(
        Contact.business_category, func.count(Contact.id)
    ).filter(
        Contact.workspace_id == ws_id,
        Contact.status == 'discovered',
        Contact.business_category.isnot(None),
    ).group_by(Contact.business_category).all()

    # Active criteria count
    active_criteria = DiscoveryCriteria.query.filter_by(
        workspace_id=ws_id, is_active=True
    ).count()

    return jsonify({
        'total': total,
        'qualified': qualified,
        'unqualified': unqualified,
        'unreviewed': total - qualified - unqualified,
        'active_criteria': active_criteria,
        'by_category': {cat: count for cat, count in categories if cat},
    })
