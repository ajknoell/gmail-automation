from datetime import datetime
from flask import Blueprint, request, jsonify, g

from app import db
from app.models.lead import Lead, LEAD_STATUSES
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.recipient import Recipient

pipeline_bp = Blueprint('pipeline', __name__)


@pipeline_bp.route('/', methods=['GET'])
def get_leads():
    """List leads with optional filtering and sorting."""
    status = request.args.get('status')
    source = request.args.get('source')
    min_score = request.args.get('min_score', type=int)
    sort_by = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    query = Lead.query.filter_by(workspace_id=g.workspace_id)

    if status:
        if ',' in status:
            query = query.filter(Lead.status.in_(status.split(',')))
        else:
            query = query.filter_by(status=status)
    if source:
        query = query.filter_by(source=source)
    if min_score is not None:
        query = query.filter(Lead.score >= min_score)

    # Sorting
    sort_col = getattr(Lead, sort_by, Lead.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    leads = query.all()
    return jsonify({'leads': [l.to_dict() for l in leads]})


@pipeline_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get pipeline statistics."""
    ws_id = g.workspace_id
    total = Lead.query.filter_by(workspace_id=ws_id).count()
    by_status = {}
    for status in LEAD_STATUSES:
        by_status[status] = Lead.query.filter_by(workspace_id=ws_id, status=status).count()

    avg_score = db.session.query(db.func.avg(Lead.score)).filter(
        Lead.workspace_id == ws_id,
        Lead.score.isnot(None),
    ).scalar()

    with_email = Lead.query.filter(
        Lead.workspace_id == ws_id,
        Lead.emails_found.isnot(None),
        Lead.emails_found != '[]',
    ).count()

    with_employee_count = Lead.query.filter(
        Lead.workspace_id == ws_id,
        Lead.employee_count.isnot(None),
    ).count()

    return jsonify({
        'total': total,
        'by_status': by_status,
        'avg_score': round(avg_score, 1) if avg_score else 0,
        'with_email': with_email,
        'with_employee_count': with_employee_count,
    })


@pipeline_bp.route('/<int:lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Get a single lead."""
    lead = Lead.query.get(lead_id)
    if not lead or lead.workspace_id != g.workspace_id:
        return jsonify({'error': 'Lead not found'}), 404
    return jsonify(lead.to_dict())


@pipeline_bp.route('/', methods=['POST'])
def create_lead():
    """Manually create a lead."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    lead = Lead(
        workspace_id=g.workspace_id,
        name=name,
        address=data.get('address'),
        phone=data.get('phone'),
        website=data.get('website'),
        place_id=data.get('place_id'),
        google_rating=data.get('google_rating'),
        review_count=data.get('review_count'),
        business_category=data.get('business_category'),
        lat=data.get('lat'),
        lng=data.get('lng'),
        source=data.get('source', 'manual'),
        status='new',
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify(lead.to_dict()), 201


@pipeline_bp.route('/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    """Update a lead."""
    lead = Lead.query.get(lead_id)
    if not lead or lead.workspace_id != g.workspace_id:
        return jsonify({'error': 'Lead not found'}), 404

    data = request.get_json() or {}
    for field in ['name', 'address', 'phone', 'website', 'business_category',
                  'employee_count', 'linkedin_url', 'decision_maker', 'status']:
        if field in data:
            setattr(lead, field, data[field])

    db.session.commit()
    return jsonify(lead.to_dict())


@pipeline_bp.route('/<int:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    """Delete a lead."""
    lead = Lead.query.get(lead_id)
    if not lead or lead.workspace_id != g.workspace_id:
        return jsonify({'error': 'Lead not found'}), 404
    db.session.delete(lead)
    db.session.commit()
    return jsonify({'success': True})


@pipeline_bp.route('/<int:lead_id>/enrich', methods=['POST'])
def enrich_lead(lead_id):
    """Trigger enrichment for a single lead."""
    lead = Lead.query.get(lead_id)
    if not lead or lead.workspace_id != g.workspace_id:
        return jsonify({'error': 'Lead not found'}), 404

    from app.services.enrichment_service import EnrichmentService

    lead.status = 'enriching'
    db.session.commit()

    try:
        results = EnrichmentService.enrich_lead(lead)
        db.session.commit()
        return jsonify({
            'lead': lead.to_dict(),
            'enrichment': results,
        })
    except Exception as e:
        lead.status = 'enriched'
        db.session.commit()
        return jsonify({'error': str(e), 'lead': lead.to_dict()}), 500


@pipeline_bp.route('/bulk-enrich', methods=['POST'])
def bulk_enrich():
    """Enrich multiple leads (or all un-enriched leads)."""
    data = request.get_json() or {}
    lead_ids = data.get('lead_ids')

    from app.services.enrichment_service import EnrichmentService

    if lead_ids:
        leads = Lead.query.filter(
            Lead.id.in_(lead_ids),
            Lead.workspace_id == g.workspace_id,
        ).all()
    else:
        leads = Lead.query.filter(
            Lead.workspace_id == g.workspace_id,
            Lead.status == 'new',
        ).order_by(Lead.created_at.asc()).limit(20).all()

    enriched = 0
    errors = 0
    for lead in leads:
        try:
            lead.status = 'enriching'
            db.session.commit()
            EnrichmentService.enrich_lead(lead)
            db.session.commit()
            enriched += 1
        except Exception as e:
            lead.status = 'enriched'
            db.session.commit()
            errors += 1

    return jsonify({'enriched': enriched, 'errors': errors, 'total': len(leads)})


@pipeline_bp.route('/<int:lead_id>/approve', methods=['POST'])
def approve_lead(lead_id):
    """Approve a lead — converts it to a Contact and optionally adds to a campaign."""
    lead = Lead.query.get(lead_id)
    if not lead or lead.workspace_id != g.workspace_id:
        return jsonify({'error': 'Lead not found'}), 404

    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    campaign_id = data.get('campaign_id')

    # Pick email: user-provided > first scraped email > placeholder
    if not email:
        emails = lead.get_emails_found()
        email = emails[0] if emails else None

    if not email:
        return jsonify({'error': 'Email is required to approve. Provide one or enrich the lead first.'}), 400

    result = {}

    # Create or update Contact
    existing_contact = Contact.query.filter_by(
        email=email, workspace_id=g.workspace_id
    ).first()

    if existing_contact:
        contact = existing_contact
        result['contact_existed'] = True
    else:
        note_parts = []
        if lead.phone:
            note_parts.append(f'Phone: {lead.phone}')
        if lead.address:
            note_parts.append(f'Address: {lead.address}')
        if lead.google_rating:
            note_parts.append(f'Rating: {lead.google_rating}')
        if lead.employee_count:
            note_parts.append(f'Employees: {lead.employee_count}')
        if lead.linkedin_url:
            note_parts.append(f'LinkedIn: {lead.linkedin_url}')
        if lead.decision_maker:
            note_parts.append(f'Decision Maker: {lead.decision_maker}')
        note_parts.append(f'Lead Score: {lead.score}')
        note_parts.append(f'Source: Pipeline ({lead.source})')

        contact = Contact(
            workspace_id=g.workspace_id,
            email=email,
            name=lead.name,
            company=lead.name,
            website=lead.website,
            phone=lead.phone,
            address=lead.address,
            notes='\n'.join(note_parts),
            status='new',
            discovery_source=lead.source,
            discovered_at=lead.created_at,
            google_rating=lead.google_rating,
            review_count=lead.review_count,
            business_category=lead.business_category,
        )
        db.session.add(contact)
        db.session.flush()
        result['contact_existed'] = False

    result['contact'] = contact.to_dict()
    lead.contact_id = contact.id
    lead.approved_at = datetime.utcnow()
    lead.status = 'approved'

    # Add to campaign if specified
    if campaign_id:
        campaign = Campaign.query.get(campaign_id)
        if campaign and campaign.workspace_id == g.workspace_id:
            existing_r = Recipient.query.filter_by(
                campaign_id=campaign_id, email=email
            ).first()
            if not existing_r:
                recipient = Recipient(
                    campaign_id=campaign_id,
                    email=email,
                    name=lead.name,
                    company=lead.name,
                )
                recipient.set_custom_fields({
                    'phone': lead.phone or '',
                    'address': lead.address or '',
                    'website': lead.website or '',
                    'rating': str(lead.google_rating) if lead.google_rating else '',
                    'employee_count': str(lead.employee_count) if lead.employee_count else '',
                    'linkedin_url': lead.linkedin_url or '',
                    'decision_maker': lead.decision_maker or '',
                    'source': 'pipeline',
                })
                db.session.add(recipient)
                campaign.total_recipients = (campaign.total_recipients or 0) + 1
                lead.campaign_id = campaign_id
                lead.status = 'in_campaign'
                result['recipient_created'] = True
            else:
                result['recipient_existed'] = True

    db.session.commit()
    return jsonify({'lead': lead.to_dict(), **result}), 200


@pipeline_bp.route('/bulk-approve', methods=['POST'])
def bulk_approve():
    """Approve multiple leads at once."""
    data = request.get_json() or {}
    lead_ids = data.get('lead_ids', [])
    campaign_id = data.get('campaign_id')

    if not lead_ids:
        return jsonify({'error': 'lead_ids required'}), 400

    leads = Lead.query.filter(
        Lead.id.in_(lead_ids),
        Lead.workspace_id == g.workspace_id,
    ).all()

    approved = 0
    skipped = 0

    for lead in leads:
        emails = lead.get_emails_found()
        email = emails[0] if emails else None

        if not email:
            skipped += 1
            continue

        # Create contact
        existing = Contact.query.filter_by(
            email=email, workspace_id=g.workspace_id
        ).first()

        if not existing:
            note_parts = []
            if lead.employee_count:
                note_parts.append(f'Employees: {lead.employee_count}')
            if lead.linkedin_url:
                note_parts.append(f'LinkedIn: {lead.linkedin_url}')
            note_parts.append(f'Lead Score: {lead.score}')

            contact = Contact(
                workspace_id=g.workspace_id,
                email=email,
                name=lead.name,
                company=lead.name,
                website=lead.website,
                phone=lead.phone,
                address=lead.address,
                notes='\n'.join(note_parts),
                status='new',
                discovery_source=lead.source,
                google_rating=lead.google_rating,
                review_count=lead.review_count,
                business_category=lead.business_category,
            )
            db.session.add(contact)
            db.session.flush()
            lead.contact_id = contact.id
        else:
            lead.contact_id = existing.id

        lead.approved_at = datetime.utcnow()
        lead.status = 'approved'

        # Add to campaign if specified
        if campaign_id:
            campaign = Campaign.query.get(campaign_id)
            if campaign and campaign.workspace_id == g.workspace_id:
                existing_r = Recipient.query.filter_by(
                    campaign_id=campaign_id, email=email
                ).first()
                if not existing_r:
                    recipient = Recipient(
                        campaign_id=campaign_id,
                        email=email,
                        name=lead.name,
                        company=lead.name,
                    )
                    recipient.set_custom_fields({
                        'phone': lead.phone or '',
                        'employee_count': str(lead.employee_count) if lead.employee_count else '',
                        'linkedin_url': lead.linkedin_url or '',
                        'source': 'pipeline',
                    })
                    db.session.add(recipient)
                    campaign.total_recipients = (campaign.total_recipients or 0) + 1
                    lead.campaign_id = campaign_id
                    lead.status = 'in_campaign'

        approved += 1

    db.session.commit()
    return jsonify({'approved': approved, 'skipped': skipped, 'total': len(leads)})


@pipeline_bp.route('/bulk-reject', methods=['POST'])
def bulk_reject():
    """Reject multiple leads at once."""
    data = request.get_json() or {}
    lead_ids = data.get('lead_ids', [])

    if not lead_ids:
        return jsonify({'error': 'lead_ids required'}), 400

    count = Lead.query.filter(
        Lead.id.in_(lead_ids),
        Lead.workspace_id == g.workspace_id,
    ).update({Lead.status: 'rejected'}, synchronize_session=False)

    db.session.commit()
    return jsonify({'rejected': count})
