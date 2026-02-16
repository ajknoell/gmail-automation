from flask import Blueprint, request, jsonify, g
from datetime import datetime
from app import db
from app.models.monitored_site import MonitoredSite
from app.models.listing import Listing
from app.models.deal_criteria import DealCriteria
from app.services.category_normalizer import normalize_category, get_standard_categories

listings_bp = Blueprint('listings', __name__)


# ─── Monitored Sites ───────────────────────────────────────────────

@listings_bp.route('/sites', methods=['GET'])
def list_sites():
    """List all monitored sites for this workspace."""
    sites = MonitoredSite.query.filter_by(workspace_id=g.workspace_id).order_by(MonitoredSite.created_at.desc()).all()
    return jsonify([s.to_dict() for s in sites])


@listings_bp.route('/sites', methods=['POST'])
def create_site():
    """Add a new site to monitor."""
    data = request.get_json() or {}

    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    site = MonitoredSite(
        workspace_id=g.workspace_id,
        name=data.get('name', '').strip() or url,
        url=url,
        contact_id=data.get('contact_id'),
        scraper_type=data.get('scraper_type', 'generic'),
        check_interval_hours=data.get('check_interval_hours', 24),
        is_active=True,
    )
    db.session.add(site)
    db.session.commit()

    return jsonify(site.to_dict()), 201


@listings_bp.route('/sites/<int:site_id>', methods=['PUT'])
def update_site(site_id):
    """Update a monitored site."""
    site = MonitoredSite.query.get_or_404(site_id)
    if site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json() or {}
    if 'name' in data:
        site.name = data['name'].strip()
    if 'url' in data:
        site.url = data['url'].strip()
    if 'contact_id' in data:
        site.contact_id = data['contact_id']
    if 'scraper_type' in data:
        site.scraper_type = data['scraper_type']
    if 'check_interval_hours' in data:
        site.check_interval_hours = data['check_interval_hours']
    if 'is_active' in data:
        site.is_active = data['is_active']

    db.session.commit()
    return jsonify(site.to_dict())


@listings_bp.route('/sites/<int:site_id>', methods=['DELETE'])
def delete_site(site_id):
    """Remove a monitored site and all its listings."""
    site = MonitoredSite.query.get_or_404(site_id)
    if site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Not found'}), 404

    db.session.delete(site)
    db.session.commit()
    return jsonify({'success': True})


@listings_bp.route('/sites/<int:site_id>/check', methods=['POST'])
def check_site_now(site_id):
    """Manually trigger a scrape for a specific site."""
    site = MonitoredSite.query.get_or_404(site_id)
    if site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Not found'}), 404

    from app.services.listing_scraper import ListingMonitor
    result = ListingMonitor.check_site(site)

    # If we got 0 listings, add helpful context
    if result.get('total_scraped', 0) == 0 and not result.get('error'):
        result['hint'] = (
            'No listings found. This site may embed listings from BizBuySell '
            'or another third-party platform that blocks automated scraping. '
            'Try adding the direct listing page URL instead.'
        )

    return jsonify(result)


@listings_bp.route('/site-info', methods=['POST'])
def fetch_site_info():
    """Fetch the site name (title tag) from a URL."""
    import requests as req
    from bs4 import BeautifulSoup

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Take the first URL if comma-separated
    first_url = url.split(',')[0].strip()

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        resp = req.get(first_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        title = ''
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Clean up common suffixes
            for sep in [' | ', ' - ', ' – ', ' — ', ' :: ']:
                if sep in title:
                    title = title.split(sep)[0].strip()

        return jsonify({'name': title, 'url': first_url})
    except Exception as e:
        return jsonify({'name': '', 'error': str(e)})


@listings_bp.route('/check-all', methods=['POST'])
def check_all_now():
    """Manually trigger a scrape for all active sites."""
    from app.services.listing_scraper import ListingMonitor

    sites = MonitoredSite.query.filter_by(
        workspace_id=g.workspace_id,
        is_active=True,
    ).all()

    results = []
    for site in sites:
        result = ListingMonitor.check_site(site)
        results.append(result)

    return jsonify(results)


# ─── Listings ──────────────────────────────────────────────────────

@listings_bp.route('', methods=['GET'])
def list_listings():
    """Get all listings across monitored sites, with optional filters.

    Query params:
        site_id       - filter to a specific site
        new_only      - only show unseen listings
        show_removed  - include delisted listings
        price_min     - minimum price in dollars (e.g. 100000)
        price_max     - maximum price in dollars (e.g. 500000)
        location      - location keyword search (case-insensitive)
        category      - category keyword search (case-insensitive)
        q             - keyword search across title + description
    """
    site_id = request.args.get('site_id', type=int)
    show_new = request.args.get('new_only', 'false').lower() == 'true'
    show_removed = request.args.get('show_removed', 'false').lower() == 'true'
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    location = request.args.get('location', '').strip()
    category = request.args.get('category', '').strip()
    keyword = request.args.get('q', '').strip()

    # Base query: join with site to filter by workspace
    query = (
        Listing.query
        .join(MonitoredSite)
        .filter(MonitoredSite.workspace_id == g.workspace_id)
    )

    if site_id:
        query = query.filter(Listing.site_id == site_id)
    if show_new:
        query = query.filter(Listing.is_new == True)
    if not show_removed:
        query = query.filter(Listing.removed_at.is_(None))

    # Price range filter
    if price_min is not None:
        query = query.filter(Listing.price_numeric >= price_min)
    if price_max is not None:
        query = query.filter(Listing.price_numeric <= price_max)

    # Financial metric filters
    for param, col in [
        ('revenue_min', Listing.revenue), ('revenue_max', Listing.revenue),
        ('sde_min', Listing.sde), ('sde_max', Listing.sde),
        ('ebitda_min', Listing.ebitda), ('ebitda_max', Listing.ebitda),
        ('cash_flow_min', Listing.cash_flow), ('cash_flow_max', Listing.cash_flow),
        ('net_profit_min', Listing.net_profit), ('net_profit_max', Listing.net_profit),
    ]:
        val = request.args.get(param, type=float)
        if val is not None:
            if param.endswith('_min'):
                query = query.filter(col >= val)
            else:
                query = query.filter(col <= val)

    # Location keyword filter (case-insensitive LIKE)
    if location:
        query = query.filter(Listing.location.ilike(f'%{location}%'))

    # Category keyword filter
    if category:
        query = query.filter(Listing.category.ilike(f'%{category}%'))

    # Keyword search across title + description
    if keyword:
        kw_pattern = f'%{keyword}%'
        query = query.filter(
            db.or_(
                Listing.title.ilike(kw_pattern),
                Listing.description.ilike(kw_pattern),
            )
        )

    listings = query.order_by(Listing.first_seen_at.desc()).all()

    # Group by site for the response
    by_site = {}
    for listing in listings:
        sid = listing.site_id
        if sid not in by_site:
            site = MonitoredSite.query.get(sid)
            by_site[sid] = {
                'site': site.to_dict() if site else {'id': sid},
                'listings': [],
            }
        by_site[sid]['listings'].append(listing.to_dict())

    return jsonify({
        'groups': list(by_site.values()),
        'total': len(listings),
        'new_count': sum(1 for l in listings if l.is_new),
    })


@listings_bp.route('/<int:listing_id>/mark-seen', methods=['POST'])
def mark_seen(listing_id):
    """Mark a listing as seen (no longer new)."""
    listing = Listing.query.get_or_404(listing_id)

    # Verify workspace ownership
    site = MonitoredSite.query.get(listing.site_id)
    if not site or site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Not found'}), 404

    listing.is_new = False
    db.session.commit()
    return jsonify(listing.to_dict())


@listings_bp.route('/mark-all-seen', methods=['POST'])
def mark_all_seen():
    """Mark all new listings as seen."""
    site_id = request.args.get('site_id', type=int)

    query = (
        Listing.query
        .join(MonitoredSite)
        .filter(
            MonitoredSite.workspace_id == g.workspace_id,
            Listing.is_new == True,
        )
    )
    if site_id:
        query = query.filter(Listing.site_id == site_id)

    count = 0
    for listing in query.all():
        listing.is_new = False
        count += 1

    db.session.commit()
    return jsonify({'marked': count})


@listings_bp.route('/<int:listing_id>/notes', methods=['PUT'])
def update_notes(listing_id):
    """Update notes on a listing."""
    listing = Listing.query.get_or_404(listing_id)

    site = MonitoredSite.query.get(listing.site_id)
    if not site or site.workspace_id != g.workspace_id:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json() or {}
    listing.notes = data.get('notes', '')
    db.session.commit()
    return jsonify(listing.to_dict())


@listings_bp.route('/filter-options', methods=['GET'])
def filter_options():
    """Get distinct values for filter dropdowns."""
    base = (
        Listing.query
        .join(MonitoredSite)
        .filter(
            MonitoredSite.workspace_id == g.workspace_id,
            Listing.removed_at.is_(None),
        )
    )

    # Distinct locations
    locations = sorted(set(
        l.location.strip()
        for l in base.filter(Listing.location.isnot(None)).with_entities(Listing.location).distinct().all()
        if l.location and l.location.strip()
    ))

    # Distinct categories (raw)
    categories = sorted(set(
        c.category.strip()
        for c in base.filter(Listing.category.isnot(None)).with_entities(Listing.category).distinct().all()
        if c.category and c.category.strip()
    ))

    # Distinct normalized categories
    normalized_categories = sorted(set(
        c.normalized_category.strip()
        for c in base.filter(Listing.normalized_category.isnot(None)).with_entities(Listing.normalized_category).distinct().all()
        if c.normalized_category and c.normalized_category.strip() and c.normalized_category.strip() != 'Other'
    ))

    # Price range
    price_min = db.session.query(db.func.min(Listing.price_numeric)).join(MonitoredSite).filter(
        MonitoredSite.workspace_id == g.workspace_id,
        Listing.removed_at.is_(None),
        Listing.price_numeric.isnot(None),
    ).scalar()

    price_max = db.session.query(db.func.max(Listing.price_numeric)).join(MonitoredSite).filter(
        MonitoredSite.workspace_id == g.workspace_id,
        Listing.removed_at.is_(None),
        Listing.price_numeric.isnot(None),
    ).scalar()

    return jsonify({
        'locations': locations,
        'categories': categories,
        'normalized_categories': normalized_categories,
        'price_min': price_min,
        'price_max': price_max,
    })


@listings_bp.route('/stats', methods=['GET'])
def listing_stats():
    """Get summary stats across all monitored sites."""
    sites = MonitoredSite.query.filter_by(workspace_id=g.workspace_id).all()

    total_sites = len(sites)
    active_sites = sum(1 for s in sites if s.is_active)
    total_listings = 0
    new_listings = 0

    for site in sites:
        total_listings += site.listings.filter(Listing.removed_at.is_(None)).count()
        new_listings += site.listings.filter_by(is_new=True).filter(Listing.removed_at.is_(None)).count()

    return jsonify({
        'total_sites': total_sites,
        'active_sites': active_sites,
        'total_listings': total_listings,
        'new_listings': new_listings,
    })


# ─── Deal Criteria ─────────────────────────────────────────────────

@listings_bp.route('/deal-criteria', methods=['GET'])
def get_deal_criteria():
    """Get the workspace's deal criteria (creates one if none exists)."""
    criteria = DealCriteria.query.filter_by(workspace_id=g.workspace_id).first()
    if not criteria:
        criteria = DealCriteria(workspace_id=g.workspace_id, is_active=False)
        db.session.add(criteria)
        db.session.commit()
    return jsonify(criteria.to_dict())


@listings_bp.route('/deal-criteria', methods=['PUT'])
def update_deal_criteria():
    """Update the workspace's deal criteria."""
    criteria = DealCriteria.query.filter_by(workspace_id=g.workspace_id).first()
    if not criteria:
        criteria = DealCriteria(workspace_id=g.workspace_id)
        db.session.add(criteria)

    data = request.get_json() or {}

    # Update all fields if present
    fields = [
        'is_active',
        'price_min', 'price_max',
        'revenue_min', 'revenue_max',
        'cash_flow_min', 'cash_flow_max',
        'sde_min', 'sde_max',
        'ebitda_min', 'ebitda_max',
        'net_profit_min', 'net_profit_max',
        'locations', 'categories',
        'include_keywords', 'exclude_keywords',
    ]
    for field in fields:
        if field in data:
            val = data[field]
            # Convert empty strings to None for numeric fields
            if field != 'is_active' and field not in ('locations', 'categories', 'include_keywords', 'exclude_keywords'):
                if val == '' or val is None:
                    val = None
                else:
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        val = None
            setattr(criteria, field, val)

    criteria.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(criteria.to_dict())


# ─── Category Normalization ───────────────────────────────────────

@listings_bp.route('/categories/standard', methods=['GET'])
def standard_categories():
    """Return the list of standard normalized categories."""
    return jsonify(get_standard_categories())


@listings_bp.route('/categories/normalize', methods=['POST'])
def normalize_category_endpoint():
    """Normalize a raw category name to a standard one."""
    data = request.get_json() or {}
    raw = data.get('category', '')
    standard, confidence = normalize_category(raw)
    return jsonify({
        'raw': raw,
        'normalized': standard,
        'confidence': round(confidence, 2),
    })


# ─── Manual Quick-Add ─────────────────────────────────────────────

@listings_bp.route('/quick-add', methods=['POST'])
def quick_add_listing():
    """Manually add a listing (for deals spotted outside of scrapers).

    Creates a 'manual' site if needed, then adds the listing.
    """
    data = request.get_json() or {}

    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    # Find or create a "Manual Entries" site for this workspace
    manual_site = MonitoredSite.query.filter_by(
        workspace_id=g.workspace_id,
        scraper_type='manual',
    ).first()

    if not manual_site:
        manual_site = MonitoredSite(
            workspace_id=g.workspace_id,
            name='Manual Entries',
            url='manual://',
            scraper_type='manual',
            is_active=False,  # Don't try to scrape it
            check_interval_hours=9999,
        )
        db.session.add(manual_site)
        db.session.flush()

    # Parse price
    price_str = data.get('price', '').strip()
    price_numeric = Listing.parse_price(price_str) if price_str else None

    # Parse financials from description
    desc = data.get('description', '').strip()
    financials = Listing.parse_financials(f"{title} {desc}") if desc else {}

    # Normalize category
    raw_cat = data.get('category', '').strip()
    norm_cat, _ = normalize_category(raw_cat) if raw_cat else ('Other', 0.0)

    # Check for duplicates
    listing_url = data.get('url', '').strip()
    content_hash = Listing.compute_hash(title, listing_url)

    existing = Listing.query.filter_by(
        site_id=manual_site.id,
        content_hash=content_hash,
    ).first()

    if existing:
        return jsonify({'error': 'This listing already exists', 'listing': existing.to_dict()}), 409

    listing = Listing(
        site_id=manual_site.id,
        title=title,
        price=price_str or None,
        price_numeric=price_numeric,
        description=desc or None,
        location=data.get('location', '').strip() or None,
        category=raw_cat or None,
        normalized_category=norm_cat,
        source='manual',
        url=listing_url or None,
        image_url=data.get('image_url', '').strip() or None,
        revenue=financials.get('revenue', {}).get('value'),
        revenue_str=financials.get('revenue', {}).get('str'),
        cash_flow=financials.get('cash_flow', {}).get('value'),
        cash_flow_str=financials.get('cash_flow', {}).get('str'),
        sde=financials.get('sde', {}).get('value'),
        sde_str=financials.get('sde', {}).get('str'),
        ebitda=financials.get('ebitda', {}).get('value'),
        ebitda_str=financials.get('ebitda', {}).get('str'),
        net_profit=financials.get('net_profit', {}).get('value'),
        net_profit_str=financials.get('net_profit', {}).get('str'),
        content_hash=content_hash,
        is_new=True,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.session.add(listing)
    db.session.commit()

    return jsonify(listing.to_dict()), 201


# ─── Email Ingestion ──────────────────────────────────────────────

@listings_bp.route('/ingest-email', methods=['POST'])
def ingest_email_listing():
    """Parse a broker email body and extract listing details.

    The frontend sends the email body text, and this endpoint uses
    regex patterns to extract title, price, location, etc.
    """
    data = request.get_json() or {}
    email_body = data.get('body', '').strip()
    email_subject = data.get('subject', '').strip()
    broker_name = data.get('broker_name', '').strip()

    if not email_body:
        return jsonify({'error': 'Email body is required'}), 400

    from app.services.email_listing_parser import parse_listing_from_email

    parsed = parse_listing_from_email(email_subject, email_body)

    if not parsed.get('title'):
        return jsonify({
            'error': 'Could not extract listing details from this email',
            'parsed': parsed,
        }), 422

    # Find or create an email-ingestion site for this workspace
    site_name = f'Email: {broker_name}' if broker_name else 'Email Ingestion'
    email_site = MonitoredSite.query.filter_by(
        workspace_id=g.workspace_id,
        scraper_type='email',
    ).first()

    if not email_site:
        email_site = MonitoredSite(
            workspace_id=g.workspace_id,
            name='Email Ingestion',
            url='email://',
            scraper_type='email',
            is_active=False,
            check_interval_hours=9999,
        )
        db.session.add(email_site)
        db.session.flush()

    # Parse financials
    financials = Listing.parse_financials(
        f"{parsed.get('title', '')} {parsed.get('description', '')}"
    )
    price_numeric = Listing.parse_price(parsed.get('price'))

    # Normalize category
    raw_cat = parsed.get('category', '')
    norm_cat, _ = normalize_category(raw_cat) if raw_cat else ('Other', 0.0)

    # Check for duplicates
    content_hash = Listing.compute_hash(parsed.get('title'), parsed.get('url'))
    existing = Listing.query.filter_by(
        site_id=email_site.id,
        content_hash=content_hash,
    ).first()

    if existing:
        return jsonify({
            'error': 'This listing was already ingested',
            'listing': existing.to_dict(),
        }), 409

    listing = Listing(
        site_id=email_site.id,
        title=parsed.get('title'),
        price=parsed.get('price'),
        price_numeric=price_numeric,
        description=parsed.get('description'),
        location=parsed.get('location'),
        category=raw_cat or None,
        normalized_category=norm_cat,
        source='email',
        url=parsed.get('url'),
        revenue=financials.get('revenue', {}).get('value'),
        revenue_str=financials.get('revenue', {}).get('str'),
        cash_flow=financials.get('cash_flow', {}).get('value'),
        cash_flow_str=financials.get('cash_flow', {}).get('str'),
        sde=financials.get('sde', {}).get('value'),
        sde_str=financials.get('sde', {}).get('str'),
        ebitda=financials.get('ebitda', {}).get('value'),
        ebitda_str=financials.get('ebitda', {}).get('str'),
        net_profit=financials.get('net_profit', {}).get('value'),
        net_profit_str=financials.get('net_profit', {}).get('str'),
        content_hash=content_hash,
        is_new=True,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.session.add(listing)
    db.session.commit()

    return jsonify({
        'listing': listing.to_dict(),
        'parsed_fields': parsed,
    }), 201


@listings_bp.route('/parse-email', methods=['POST'])
def parse_email_preview():
    """Preview what would be extracted from a broker email (dry-run).

    Returns parsed fields without saving anything.
    """
    data = request.get_json() or {}
    email_body = data.get('body', '').strip()
    email_subject = data.get('subject', '').strip()

    if not email_body:
        return jsonify({'error': 'Email body is required'}), 400

    from app.services.email_listing_parser import parse_listing_from_email

    parsed = parse_listing_from_email(email_subject, email_body)

    # Normalize category
    if parsed.get('category'):
        norm, conf = normalize_category(parsed['category'])
        parsed['normalized_category'] = norm
        parsed['category_confidence'] = round(conf, 2)

    return jsonify(parsed)


# ─── Auto Gmail Alert Scanning ────────────────────────────────────

@listings_bp.route('/scan-email-alerts', methods=['POST'])
def scan_email_alerts():
    """Scan Gmail inbox for BizBuySell and broker alert emails.

    Automatically finds saved search alert emails, extracts listing
    data, and saves new listings.
    """
    data = request.get_json() or {}
    days_back = data.get('days_back', 7)
    custom_query = data.get('custom_query', '')

    from app.services.email_alert_scanner import EmailAlertScanner

    result = EmailAlertScanner.scan_inbox(
        workspace_id=g.workspace_id,
        days_back=days_back,
        custom_query=custom_query.strip() or None,
    )

    return jsonify(result)
