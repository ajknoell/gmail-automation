from flask import Blueprint, request, jsonify, g

from app import db
from app.models.settings import Settings
from app.models.contact import Contact
from app.models.recipient import Recipient
from app.models.campaign import Campaign

map_explorer_bp = Blueprint('map_explorer', __name__)


def _get_places_service():
    """Instantiate PlacesService with the stored API key."""
    from app.services.places_service import PlacesService

    api_key = Settings.get('google_places_api_key')
    if not api_key:
        return None
    return PlacesService(api_key)


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
    """Search for nearby businesses using Places API (New)."""
    data = request.get_json() or {}
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required'}), 400

    svc = _get_places_service()
    if not svc:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400

    try:
        results = svc.search_nearby(
            lat=lat,
            lng=lng,
            radius=data.get('radius', 5000),
            included_type=data.get('type', ''),
            included_types=data.get('types') or None,
            keyword=data.get('keyword', ''),
            min_rating=data.get('min_rating', 0),
            max_results=data.get('max_results', 20),
        )
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@map_explorer_bp.route('/text-search', methods=['POST'])
def text_search():
    """Search for businesses using a free-form text query (Places Text Search API).

    Supports niche queries like "mobile dog groomer", "vegan bakery near me", etc.
    """
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()
    lat = data.get('lat')
    lng = data.get('lng')
    if not query:
        return jsonify({'error': 'query is required'}), 400
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required'}), 400

    svc = _get_places_service()
    if not svc:
        return jsonify({'error': 'Google Places API key not configured. Go to Settings.'}), 400

    try:
        results = svc.search_text(
            query=query,
            lat=lat,
            lng=lng,
            radius=data.get('radius', 5000),
            min_rating=data.get('min_rating', 0),
            max_results=data.get('max_results', 20),
        )
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
