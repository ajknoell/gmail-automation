"""
Prospect Discovery — finds business leads automatically via Google Maps
scraping and contact page extraction. Zero external API cost.
"""
import re
import time
import threading
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# Shared lock to prevent multiple Playwright browsers running simultaneously
_playwright_lock = threading.Lock()

# Free email providers to filter out
FREE_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'mail.com', 'protonmail.com', 'zoho.com', 'yandex.com',
    'live.com', 'msn.com', 'comcast.net', 'verizon.net', 'att.net',
    'me.com', 'mac.com', 'gmx.com', 'inbox.com',
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})')


class ProspectDiscovery:
    """Discovers business prospects via Google Maps scraping + contact page extraction."""

    @classmethod
    def search_google_maps(cls, query, location, max_results=20):
        """
        Use Playwright to search Google Maps and extract business listings.

        Args:
            query: Business type (e.g., "plumber", "restaurant")
            location: Zip code or city name
            max_results: Maximum businesses to extract

        Returns:
            List of dicts with business info
        """
        from app.services.listing_scraper import fetch_page_with_playwright

        search_url = f'https://www.google.com/maps/search/{query}+{location}'
        businesses = []

        try:
            with _playwright_lock:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=['--disable-blink-features=AutomationControlled'],
                    )
                    ctx = browser.new_context(
                        user_agent=(
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/120.0.0.0 Safari/537.36'
                        ),
                        viewport={'width': 1400, 'height': 900},
                        locale='en-US',
                    )
                    page = ctx.new_page()

                    # Remove webdriver detection
                    page.add_init_script('''
                        Object.defineProperty(navigator, "webdriver", {get: () => undefined});
                    ''')

                    page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    page.wait_for_timeout(3000)

                    # Scroll the results panel to load more
                    results_panel = page.query_selector('[role="feed"]')
                    if results_panel:
                        for _ in range(min(max_results // 5, 6)):
                            results_panel.evaluate('el => el.scrollBy(0, 800)')
                            page.wait_for_timeout(1500)

                    # Extract business cards
                    items = page.query_selector_all('[data-result-index], .Nv2PK')
                    for item in items[:max_results]:
                        try:
                            business = cls._extract_maps_business(item, page)
                            if business and business.get('name'):
                                businesses.append(business)
                        except Exception:
                            continue

                    browser.close()

        except Exception as e:
            logger.error(f'Google Maps scraping error: {e}')

        return businesses

    @classmethod
    def _extract_maps_business(cls, item, page):
        """Extract business data from a Google Maps result card."""
        business = {}

        # Name
        name_el = item.query_selector('.qBF1Pd, .fontHeadlineSmall')
        if name_el:
            business['name'] = name_el.inner_text().strip()

        # Rating and review count
        rating_el = item.query_selector('.MW4etd')
        if rating_el:
            try:
                business['rating'] = float(rating_el.inner_text().strip())
            except (ValueError, TypeError):
                pass

        review_el = item.query_selector('.UY7F9')
        if review_el:
            text = review_el.inner_text().strip()
            nums = re.findall(r'[\d,]+', text)
            if nums:
                try:
                    business['review_count'] = int(nums[0].replace(',', ''))
                except (ValueError, TypeError):
                    pass

        # Category
        cat_el = item.query_selector('.W4Efsd:nth-child(1) .W4Efsd span:nth-child(1)')
        if cat_el:
            business['category'] = cat_el.inner_text().strip().strip('·').strip()

        # Address
        addr_els = item.query_selector_all('.W4Efsd')
        for el in addr_els:
            text = el.inner_text().strip()
            # Address usually contains a number and street
            if re.search(r'\d{1,5}\s+\w', text) and 'star' not in text.lower():
                business['address'] = text.split('·')[0].strip()
                break

        # Phone
        for el in addr_els:
            text = el.inner_text().strip()
            phone_match = PHONE_RE.search(text)
            if phone_match:
                business['phone'] = phone_match.group(0)
                break

        # Website (from the action buttons)
        website_btn = item.query_selector('a[data-value="Website"], a[aria-label*="Website"]')
        if website_btn:
            href = website_btn.get_attribute('href')
            if href and not href.startswith('https://www.google.com'):
                business['website'] = href

        return business

    @classmethod
    def extract_contact_info(cls, website_url):
        """
        Visit a business website and extract emails and phones from
        the main page plus /contact, /about pages.

        Returns:
            {emails: [str], phones: [str]}
        """
        if not website_url:
            return {'emails': [], 'phones': []}

        # Ensure URL has scheme
        if not website_url.startswith('http'):
            website_url = f'https://{website_url}'

        all_emails = set()
        all_phones = set()
        pages_to_check = [website_url]

        # Build inner page URLs
        parsed = urlparse(website_url)
        base = f'{parsed.scheme}://{parsed.netloc}'
        for path in ['/contact', '/contact-us', '/about', '/about-us', '/team']:
            pages_to_check.append(urljoin(base, path))

        for url in pages_to_check:
            try:
                import requests
                resp = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    text = resp.text

                    # Extract emails
                    emails = EMAIL_RE.findall(text)
                    for email in emails:
                        domain = email.split('@')[1].lower()
                        if domain not in FREE_EMAIL_DOMAINS:
                            all_emails.add(email.lower())

                    # Extract phones
                    phones = PHONE_RE.findall(text)
                    for phone in phones:
                        all_phones.add(phone)

                time.sleep(1)  # Rate limiting
            except Exception:
                continue

        return {
            'emails': list(all_emails)[:5],
            'phones': list(all_phones)[:3],
        }

    @classmethod
    def run_discovery(cls, criteria, workspace_id):
        """
        Full discovery pipeline for one DiscoveryCriteria.

        Returns:
            {found: int, new: int, skipped_duplicates: int, errors: int}
        """
        from app import db
        from app.models.contact import Contact

        queries = criteria.get_search_queries()
        zip_codes = criteria.get_zip_codes()

        if not queries or not zip_codes:
            return {'found': 0, 'new': 0, 'skipped_duplicates': 0, 'errors': 0}

        found = 0
        new = 0
        skipped = 0
        errors = 0

        for query in queries:
            for zip_code in zip_codes:
                try:
                    businesses = cls.search_google_maps(
                        query, zip_code,
                        max_results=criteria.max_results_per_query or 20,
                    )

                    for biz in businesses:
                        found += 1

                        # Filter by minimum rating
                        if criteria.min_rating and biz.get('rating', 0) < criteria.min_rating:
                            continue

                        # Deduplicate: check by name+address or email
                        name = biz.get('name', '').strip()
                        address = biz.get('address', '').strip()

                        if name:
                            existing = Contact.query.filter_by(
                                workspace_id=workspace_id,
                                company=name,
                            ).first()
                            if existing:
                                skipped += 1
                                continue

                        # Enrich with contact info from website
                        contact_info = {'emails': [], 'phones': []}
                        if biz.get('website'):
                            try:
                                contact_info = cls.extract_contact_info(biz['website'])
                            except Exception:
                                pass

                        # Use first business email found, or skip if none
                        email = None
                        if contact_info['emails']:
                            email = contact_info['emails'][0]
                        elif biz.get('phone'):
                            # Create placeholder email from phone for tracking
                            email = None  # Will use phone-only contact

                        # Check email duplicate
                        if email:
                            existing = Contact.query.filter_by(
                                workspace_id=workspace_id,
                                email=email,
                            ).first()
                            if existing:
                                skipped += 1
                                continue

                        # Create contact
                        contact = Contact(
                            workspace_id=workspace_id,
                            email=email or f'{name.lower().replace(" ", ".")}@unknown.com',
                            name=name,
                            company=name,
                            website=biz.get('website'),
                            status='discovered',
                            discovery_source='google_maps',
                            discovered_at=datetime.utcnow(),
                            google_rating=biz.get('rating'),
                            review_count=biz.get('review_count'),
                            phone=biz.get('phone') or (contact_info['phones'][0] if contact_info['phones'] else None),
                            address=address,
                            business_category=biz.get('category'),
                            discovery_criteria_id=criteria.id,
                        )
                        db.session.add(contact)
                        new += 1

                    db.session.commit()

                except Exception as e:
                    logger.error(f'Discovery error for {query} in {zip_code}: {e}')
                    db.session.rollback()
                    errors += 1

                # Rate limiting between queries
                time.sleep(2)

        # Update last scanned time
        criteria.last_scanned_at = datetime.utcnow()
        db.session.commit()

        return {'found': found, 'new': new, 'skipped_duplicates': skipped, 'errors': errors}


class ProspectScanner:
    """Background poller that runs discovery on a schedule."""
    _thread = None

    @classmethod
    def check_all_due(cls):
        """Check all active DiscoveryCriteria that are due for scanning."""
        from app import db
        from app.models.discovery_criteria import DiscoveryCriteria

        now = datetime.utcnow()
        criteria_list = DiscoveryCriteria.query.filter_by(is_active=True).all()

        results = []
        for criteria in criteria_list:
            # Check if due
            if criteria.last_scanned_at:
                next_scan = criteria.last_scanned_at + timedelta(hours=criteria.scan_interval_hours)
                if now < next_scan:
                    continue

            try:
                result = ProspectDiscovery.run_discovery(criteria, criteria.workspace_id)
                results.append({
                    'criteria_id': criteria.id,
                    'criteria_name': criteria.name,
                    **result,
                })
                logger.info(f'Discovery scan complete for "{criteria.name}": {result}')
            except Exception as e:
                logger.error(f'Discovery scan failed for "{criteria.name}": {e}')

        return results

    @classmethod
    def start_background_polling(cls, app, interval=3600):
        """Start a daemon thread that polls for due discovery scans."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        cls.check_all_due()
                    except Exception as e:
                        app.logger.error(f'Prospect scanner error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Prospect scanner started (interval={interval}s)')
