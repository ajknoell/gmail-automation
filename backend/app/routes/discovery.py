"""
Discovery routes — manage search criteria, discovered prospects, and
configurable discovery sources (state licenses, Google Maps, Yelp, etc.).
"""
import json
import logging
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify, g, current_app

from app import db
from app.models.discovery_criteria import DiscoveryCriteria
from app.models.discovery_source import DiscoverySource, SOURCE_TYPES, SCHEDULE_OPTIONS
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.recipient import Recipient

logger = logging.getLogger(__name__)

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


# ---------- Discovery Sources (Cowork M&A list building) ----------


@discovery_bp.route('/sources', methods=['GET'])
def list_sources() -> tuple:
    """List configured discovery sources for the workspace."""
    sources = DiscoverySource.query.filter_by(
        workspace_id=g.workspace_id
    ).order_by(DiscoverySource.updated_at.desc()).all()
    return jsonify({'sources': [s.to_dict() for s in sources]})


@discovery_bp.route('/sources/available', methods=['GET'])
def list_available_scrapers() -> tuple:
    """List available scraper types and their supported configurations."""
    from app.services.scrapers.state_license_scraper import get_available_states
    return jsonify({
        'state_license_scrapers': get_available_states(),
        'source_types': SOURCE_TYPES,
        'schedule_options': SCHEDULE_OPTIONS,
    })


@discovery_bp.route('/sources', methods=['POST'])
def create_source() -> tuple:
    """Create a new discovery source.

    Example body for state license source:
    {
        "name": "CA HVAC Contractors",
        "source_type": "state_license",
        "config": {"state_source_id": "cslb_ca", "license_type": "C-20", "location": "Los Angeles"},
        "schedule": "weekly",
        "thesis_id": 1
    }
    """
    data = request.get_json() or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Source name is required'}), 400

    source_type = data.get('source_type')
    if source_type not in SOURCE_TYPES:
        return jsonify({'error': f'Invalid source_type. Must be one of: {", ".join(SOURCE_TYPES)}'}), 400

    schedule = data.get('schedule', 'manual')
    if schedule not in SCHEDULE_OPTIONS:
        return jsonify({'error': f'Invalid schedule. Must be one of: {", ".join(SCHEDULE_OPTIONS)}'}), 400

    source = DiscoverySource(
        workspace_id=g.workspace_id,
        thesis_id=data.get('thesis_id'),
        name=name,
        source_type=source_type,
        schedule=schedule,
        is_active=data.get('is_active', True),
    )
    source.set_config(data.get('config', {}))

    db.session.add(source)
    db.session.commit()
    return jsonify(source.to_dict()), 201


@discovery_bp.route('/sources/<int:source_id>', methods=['PUT'])
def update_source(source_id: int) -> tuple:
    """Update an existing discovery source."""
    source = DiscoverySource.query.filter_by(
        id=source_id, workspace_id=g.workspace_id
    ).first()
    if not source:
        return jsonify({'error': 'Source not found'}), 404

    data = request.get_json() or {}

    if 'name' in data:
        source.name = data['name']
    if 'config' in data:
        source.set_config(data['config'])
    if 'schedule' in data:
        if data['schedule'] not in SCHEDULE_OPTIONS:
            return jsonify({'error': f'Invalid schedule'}), 400
        source.schedule = data['schedule']
    if 'is_active' in data:
        source.is_active = data['is_active']
    if 'thesis_id' in data:
        source.thesis_id = data['thesis_id']

    db.session.commit()
    return jsonify(source.to_dict())


@discovery_bp.route('/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id: int) -> tuple:
    """Delete a discovery source."""
    source = DiscoverySource.query.filter_by(
        id=source_id, workspace_id=g.workspace_id
    ).first()
    if not source:
        return jsonify({'error': 'Source not found'}), 404
    db.session.delete(source)
    db.session.commit()
    return jsonify({'success': True})


@discovery_bp.route('/sources/<int:source_id>/run', methods=['POST'])
def run_source(source_id: int) -> tuple:
    """Trigger an immediate run of a discovery source."""
    source = DiscoverySource.query.filter_by(
        id=source_id, workspace_id=g.workspace_id
    ).first()
    if not source:
        return jsonify({'error': 'Source not found'}), 404

    app = current_app._get_current_object()
    ws_id = g.workspace_id
    sid = source.id

    def run_in_background() -> None:
        """Execute the discovery source scraping in a background thread."""
        with app.app_context():
            _execute_source(sid, ws_id)

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': f'Running source "{source.name}" in background'})


def _execute_source(source_id: int, workspace_id: int) -> None:
    """Execute a discovery source and create leads from results.

    Args:
        source_id: ID of the DiscoverySource to run
        workspace_id: Workspace context
    """
    source = DiscoverySource.query.get(source_id)
    if not source:
        return

    config = source.get_config()
    results = []

    try:
        if source.source_type == 'state_license':
            from app.services.scrapers.state_license_scraper import search_state_licenses
            results = search_state_licenses(
                state_source_id=config.get('state_source_id', ''),
                license_type=config.get('license_type', ''),
                location=config.get('location', ''),
                max_results=config.get('max_results', 50),
            )
        # Future: google_maps, yelp, industry_dir handlers

        # Convert results to leads
        created = 0
        for biz in results:
            # Dedup by license number or name+address
            existing = None
            if biz.license_number:
                existing = Lead.query.filter_by(
                    workspace_id=workspace_id,
                    license_number=biz.license_number,
                ).first()
            if not existing and biz.name:
                existing = Lead.query.filter_by(
                    workspace_id=workspace_id,
                    name=biz.name,
                    address=biz.address,
                ).first()

            if existing:
                continue

            lead = Lead(
                workspace_id=workspace_id,
                name=biz.name,
                address=biz.address,
                phone=biz.phone,
                website=biz.website,
                owner_name=biz.owner_name,
                license_number=biz.license_number,
                license_status=biz.license_status,
                license_issue_date=biz.license_issue_date,
                business_category=config.get('license_type', ''),
                source=f'state_license_{biz.source}',
                status='new',
            )
            lead.set_data_sources([biz.source])
            db.session.add(lead)
            created += 1

        source.last_run_at = datetime.utcnow()
        source.last_error = None
        source.results_count = created
        source.total_results_count = (source.total_results_count or 0) + created
        db.session.commit()

        logger.info(f"Discovery source {source.name}: created {created} new leads from {len(results)} results")

    except Exception as e:
        logger.error(f"Discovery source {source.name} failed: {e}", exc_info=True)
        source.last_error = str(e)[:500]
        source.last_run_at = datetime.utcnow()
        db.session.commit()
