"""Apollo.io integration routes for contact search and import."""

import logging

from flask import Blueprint, g, jsonify, request

from app import db
from app.models import Campaign, Contact, Recipient, Settings, Tag

logger = logging.getLogger(__name__)

apollo_bp = Blueprint('apollo', __name__)


@apollo_bp.route('/status', methods=['GET'])
def get_status() -> tuple:
    """Check if Apollo API key is configured."""
    key = Settings.get('apollo_api_key', '')
    return jsonify({'configured': bool(key and len(key) > 5)})


@apollo_bp.route('/search', methods=['POST'])
def search_people() -> tuple:
    """Search Apollo for people matching given filters.

    Expects JSON body with optional fields: person_titles, person_locations,
    q_organization_domains, q_keywords, page, per_page.
    """
    from app.services.apollo_service import ApolloService

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    try:
        result = ApolloService.search_people(
            person_titles=data.get('person_titles'),
            person_locations=data.get('person_locations'),
            q_organization_domains=data.get('q_organization_domains'),
            q_keywords=data.get('q_keywords'),
            page=data.get('page', 1),
            per_page=data.get('per_page', 25),
        )

        people = [
            ApolloService.map_to_contact(p)
            for p in result.get('people', [])
        ]
        pagination = result.get('pagination', {})

        return jsonify({
            'people': people,
            'total': pagination.get('total_entries', 0),
            'page': pagination.get('page', 1),
            'per_page': pagination.get('per_page', 25),
            'total_pages': pagination.get('total_pages', 0),
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Apollo search failed: {e}")
        return jsonify({'error': 'Apollo search failed. Check your API key.'}), 502


@apollo_bp.route('/import/contacts', methods=['POST'])
def import_to_contacts() -> tuple:
    """Import selected Apollo people into the Contacts directory.

    Expects JSON body with 'people' array and optional 'tag' string.
    """
    data = request.get_json()
    if not data or not data.get('people'):
        return jsonify({'error': 'No people provided'}), 400

    imported = 0
    skipped = 0

    for person in data['people']:
        email = (person.get('email') or '').strip().lower()
        if not email or '@' not in email:
            skipped += 1
            continue

        existing = Contact.query.filter_by(
            email=email, workspace_id=g.workspace_id
        ).first()
        if existing:
            skipped += 1
            continue

        contact = Contact(
            email=email,
            name=person.get('name', ''),
            company=person.get('company', ''),
            website=person.get('website', ''),
            phone=person.get('phone', ''),
            address=person.get('address', ''),
            business_category=person.get('business_category', ''),
            workspace_id=g.workspace_id,
            discovery_source='apollo',
            status='discovered',
        )
        db.session.add(contact)
        imported += 1

    db.session.commit()

    tag_name = data.get('tag')
    if tag_name and imported > 0:
        tag = Tag.query.filter_by(
            name=tag_name, workspace_id=g.workspace_id
        ).first()
        if not tag:
            tag = Tag(name=tag_name, workspace_id=g.workspace_id)
            db.session.add(tag)
            db.session.flush()

        new_contacts = Contact.query.filter_by(
            workspace_id=g.workspace_id,
            discovery_source='apollo',
        ).order_by(Contact.created_at.desc()).limit(imported).all()

        for c in new_contacts:
            if tag not in c.tags:
                c.tags.append(tag)
        db.session.commit()

    return jsonify({
        'success': True,
        'imported': imported,
        'skipped': skipped,
    })


@apollo_bp.route('/import/campaign', methods=['POST'])
def import_to_campaign() -> tuple:
    """Import selected Apollo people as campaign recipients.

    Expects JSON body with 'campaign_id' and 'people' array.
    """
    data = request.get_json()
    if not data or not data.get('people'):
        return jsonify({'error': 'No people provided'}), 400

    campaign_id = data.get('campaign_id')
    if not campaign_id:
        return jsonify({'error': 'campaign_id is required'}), 400

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    if campaign.status not in ('draft', 'paused'):
        return jsonify({'error': 'Cannot add recipients to active campaign'}), 400

    imported = 0
    skipped = 0

    for person in data['people']:
        email = (person.get('email') or '').strip()
        if not email or '@' not in email:
            skipped += 1
            continue

        existing = Recipient.query.filter_by(
            campaign_id=campaign.id, email=email
        ).first()
        if existing:
            skipped += 1
            continue

        custom_fields = {}
        for key in ('title', 'linkedin_url', 'phone', 'website',
                     'business_category', 'apollo_id'):
            if person.get(key):
                custom_fields[key] = person[key]

        recipient = Recipient(
            campaign_id=campaign.id,
            email=email,
            name=person.get('name', ''),
            company=person.get('company', ''),
        )
        recipient.set_custom_fields(custom_fields)
        db.session.add(recipient)
        imported += 1

    campaign.total_recipients = Recipient.query.filter_by(
        campaign_id=campaign.id
    ).count() + imported
    db.session.commit()

    return jsonify({
        'success': True,
        'campaign_id': campaign.id,
        'imported': imported,
        'skipped': skipped,
    })
