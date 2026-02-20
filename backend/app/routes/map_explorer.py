from flask import Blueprint, request, jsonify, g

from app import db
from app.models.settings import Settings
from app.models.contact import Contact
from app.models.recipient import Recipient
from app.models.campaign import Campaign
from app.models.lead import Lead

map_explorer_bp = Blueprint('map_explorer', __name__)


def _get_places_service():
    """Instantiate PlacesService with the stored API key."""
    from app.services.places_service import PlacesService

    api_key = Settings.get('google_places_api_key')
    if not api_key:
        return None
    return PlacesService(api_key)


def _get_yelp_service():
    """Instantiate YelpService with the stored API key."""
    from app.services.yelp_service import YelpService

    api_key = Settings.get('yelp_api_key')
    if not api_key:
        return None
    return YelpService(api_key)


@map_explorer_bp.route('/maps-js-key', methods=['GET'])
def maps_js_key():
    """Return the Google API key for the Maps JavaScript API.

    This key is inherently browser-exposed (same as embedding in HTML).
    Security is enforced via HTTP referer restrictions in Google Cloud Console.
    """
    key = Settings.get('google_places_api_key')
    if not key:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400
    return jsonify({'key': key})


@map_explorer_bp.route('/geocode', methods=['GET'])
def geocode():
    """Convert a city/address string to lat/lng coordinates."""
    address = request.args.get('address', '').strip()
    if not address:
        return jsonify({'error': 'address parameter is required'}), 400

    svc = _get_places_service()
    if not svc:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400

    result = svc.geocode(address)
    if not result:
        return jsonify({'error': f'Could not geocode "{address}"'}), 404

    return jsonify(result)


@map_explorer_bp.route('/search', methods=['POST'])
def search_nearby():
    """Search for nearby businesses using Places API (New) + optional Yelp."""
    data = request.get_json() or {}
    lat = data.get('lat')
    lng = data.get('lng')
    include_yelp = data.get('include_yelp', True)
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required'}), 400

    svc = _get_places_service()
    if not svc:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400

    radius = data.get('radius', 5000)
    min_rating = data.get('min_rating', 0)
    max_results = data.get('max_results', 20)
    types_list = data.get('types') or ([data.get('type', '')] if data.get('type') else [])

    try:
        google_results = svc.search_nearby(
            lat=lat,
            lng=lng,
            radius=radius,
            included_type=data.get('type', ''),
            included_types=data.get('types') or None,
            keyword=data.get('keyword', ''),
            min_rating=min_rating,
            max_results=max_results,
        )

        # Merge with Yelp if configured
        yelp_results = []
        yelp_svc = _get_yelp_service() if include_yelp else None
        if yelp_svc:
            try:
                from app.services.yelp_service import YelpService
                yelp_categories = YelpService.google_types_to_yelp_categories(
                    [t for t in types_list if t]
                )
                yelp_results = yelp_svc.search_businesses(
                    lat=lat, lng=lng,
                    radius=radius,
                    categories=yelp_categories or None,
                    min_rating=min_rating,
                    max_results=max_results,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'Yelp search failed (non-fatal): {e}')

        if yelp_results:
            from app.services.business_search import merge_results
            results = merge_results(google_results, yelp_results)
        else:
            # Tag with source
            for r in google_results:
                r.setdefault('source', 'google')
                r.setdefault('sources', ['google'])
            results = google_results

        return jsonify({
            'results': results,
            'sources': {
                'google': len(google_results),
                'yelp': len(yelp_results),
                'total': len(results),
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@map_explorer_bp.route('/text-search', methods=['POST'])
def text_search():
    """Search for businesses using a free-form text query (Places Text Search API).

    Supports niche queries like "mobile dog groomer", "vegan bakery near me", etc.
    Merges with Yelp results when Yelp API key is configured.
    """
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()
    lat = data.get('lat')
    lng = data.get('lng')
    include_yelp = data.get('include_yelp', True)
    if not query:
        return jsonify({'error': 'query is required'}), 400
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required'}), 400

    svc = _get_places_service()
    if not svc:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400

    radius = data.get('radius', 5000)
    min_rating = data.get('min_rating', 0)
    max_results = data.get('max_results', 20)

    try:
        google_results = svc.search_text(
            query=query,
            lat=lat,
            lng=lng,
            radius=radius,
            min_rating=min_rating,
            max_results=max_results,
        )

        # Merge with Yelp if configured
        yelp_results = []
        yelp_svc = _get_yelp_service() if include_yelp else None
        if yelp_svc:
            try:
                yelp_results = yelp_svc.search_businesses(
                    lat=lat, lng=lng,
                    radius=radius,
                    term=query,
                    min_rating=min_rating,
                    max_results=max_results,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'Yelp text search failed (non-fatal): {e}')

        if yelp_results:
            from app.services.business_search import merge_results
            results = merge_results(google_results, yelp_results)
        else:
            for r in google_results:
                r.setdefault('source', 'google')
                r.setdefault('sources', ['google'])
            results = google_results

        return jsonify({
            'results': results,
            'sources': {
                'google': len(google_results),
                'yelp': len(yelp_results),
                'total': len(results),
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@map_explorer_bp.route('/sources', methods=['GET'])
def get_configured_sources():
    """Return which data sources are configured (have API keys)."""
    return jsonify({
        'google': bool(Settings.get('google_places_api_key')),
        'yelp': bool(Settings.get('yelp_api_key')),
    })


@map_explorer_bp.route('/add-to-outreach', methods=['POST'])
def add_to_outreach():
    """Add a business from map results to outreach (Contact and/or Recipient)."""
    data = request.get_json() or {}
    action = data.get('action', 'contact')  # 'contact', 'recipient', or 'both'
    email = (data.get('email') or '').strip().lower()
    name = data.get('name', '')
    company = name  # Business name is the company
    website = data.get('website', '')
    phone = data.get('phone', '')
    address = data.get('address', '')
    place_id = data.get('place_id', '')
    rating = data.get('rating')
    campaign_id = data.get('campaign_id')
    notes = data.get('notes', '')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    result = {}

    if action in ('contact', 'both'):
        existing = Contact.query.filter_by(
            email=email, workspace_id=g.workspace_id
        ).first()
        if existing:
            result['contact'] = existing.to_dict()
            result['contact_existed'] = True
        else:
            note_parts = []
            if phone:
                note_parts.append(f'Phone: {phone}')
            if address:
                note_parts.append(f'Address: {address}')
            if rating:
                note_parts.append(f'Rating: {rating}')
            if place_id:
                note_parts.append(f'Place ID: {place_id}')
            note_parts.append('Source: Map Explorer')
            if notes:
                note_parts.append(notes)

            contact = Contact(
                workspace_id=g.workspace_id,
                email=email,
                name=name,
                company=company,
                website=website,
                notes='\n'.join(note_parts),
                status='new',
            )
            db.session.add(contact)
            db.session.flush()
            result['contact'] = contact.to_dict()
            result['contact_existed'] = False

    if action in ('recipient', 'both'):
        if not campaign_id:
            return jsonify({'error': 'campaign_id is required for recipient action'}), 400
        campaign = Campaign.query.get(campaign_id)
        if not campaign or campaign.workspace_id != g.workspace_id:
            return jsonify({'error': 'Campaign not found'}), 404

        existing_r = Recipient.query.filter_by(
            campaign_id=campaign_id, email=email
        ).first()
        if existing_r:
            result['recipient'] = existing_r.to_dict()
            result['recipient_existed'] = True
        else:
            recipient = Recipient(
                campaign_id=campaign_id,
                email=email,
                name=name,
                company=company,
            )
            recipient.set_custom_fields({
                'phone': phone,
                'address': address,
                'website': website,
                'rating': str(rating) if rating else '',
                'place_id': place_id,
                'source': 'map_explorer',
            })
            recipient.notes = notes
            db.session.add(recipient)
            campaign.total_recipients = (campaign.total_recipients or 0) + 1
            db.session.flush()
            result['recipient'] = recipient.to_dict()
            result['recipient_existed'] = False

    db.session.commit()
    return jsonify(result), 201


@map_explorer_bp.route('/add-to-pipeline', methods=['POST'])
def add_to_pipeline():
    """Add a business from map results directly into the lead pipeline for enrichment."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Business name is required'}), 400

    place_id = data.get('place_id', '')

    # Check for duplicate by place_id
    if place_id:
        existing = Lead.query.filter_by(
            workspace_id=g.workspace_id, place_id=place_id
        ).first()
        if existing:
            return jsonify({'lead': existing.to_dict(), 'existed': True}), 200

    # Check for duplicate by name + address
    address = data.get('address', '')
    if address:
        existing = Lead.query.filter_by(
            workspace_id=g.workspace_id, name=name, address=address
        ).first()
        if existing:
            return jsonify({'lead': existing.to_dict(), 'existed': True}), 200

    lead = Lead(
        workspace_id=g.workspace_id,
        name=name,
        address=address,
        phone=data.get('phone', ''),
        website=data.get('website', ''),
        place_id=place_id,
        google_rating=data.get('rating'),
        review_count=data.get('user_ratings_total'),
        business_category=data.get('primary_type', ''),
        lat=data.get('lat'),
        lng=data.get('lng'),
        source='map_explorer',
        status='new',
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify({'lead': lead.to_dict(), 'existed': False}), 201


@map_explorer_bp.route('/bulk-add-to-pipeline', methods=['POST'])
def bulk_add_to_pipeline():
    """Add multiple businesses from map results to the pipeline at once."""
    data = request.get_json() or {}
    businesses = data.get('businesses', [])

    if not businesses:
        return jsonify({'error': 'businesses array is required'}), 400

    added = 0
    skipped = 0

    for biz in businesses:
        name = (biz.get('name') or '').strip()
        if not name:
            continue

        place_id = biz.get('place_id', '')

        # Duplicate check
        if place_id:
            existing = Lead.query.filter_by(
                workspace_id=g.workspace_id, place_id=place_id
            ).first()
            if existing:
                skipped += 1
                continue

        lead = Lead(
            workspace_id=g.workspace_id,
            name=name,
            address=biz.get('address', ''),
            phone=biz.get('phone', ''),
            website=biz.get('website', ''),
            place_id=place_id,
            google_rating=biz.get('rating'),
            review_count=biz.get('user_ratings_total'),
            business_category=biz.get('primary_type', ''),
            lat=biz.get('lat'),
            lng=biz.get('lng'),
            source='map_explorer',
            status='new',
        )
        db.session.add(lead)
        added += 1

    db.session.commit()
    return jsonify({'added': added, 'skipped': skipped}), 201
