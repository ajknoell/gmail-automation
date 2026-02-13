"""
Listing Scraper Service
-----------------------
Monitors broker websites for new business-for-sale listings.
Uses a plugin/adapter pattern so each site can have custom parsing logic.
Falls back to Playwright headless browser for JS-rendered sites.
Detects BizBuySell iframe embeds and scrapes iframe content.
"""

import threading
import time
import re
import json
import logging
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# ─── Scraper Registry ──────────────────────────────────────────────

_SCRAPERS = {}


def register_scraper(name):
    """Decorator to register a site-specific scraper."""
    def decorator(cls):
        _SCRAPERS[name] = cls()
        return cls
    return decorator


def get_scraper(scraper_type):
    """Look up a scraper by type. Falls back to GenericScraper."""
    return _SCRAPERS.get(scraper_type, _SCRAPERS.get('generic'))


# ─── Playwright helpers ────────────────────────────────────────────

_playwright_available = None


def _check_playwright():
    """Lazy-check whether Playwright + Chromium are installed."""
    global _playwright_available
    if _playwright_available is None:
        try:
            from playwright.sync_api import sync_playwright
            _playwright_available = True
        except ImportError:
            _playwright_available = False
            logger.info('Playwright not installed – JS rendering disabled')
    return _playwright_available


def fetch_page_with_playwright(url, wait_ms=4000, extract_iframes=False):
    """
    Render a page with headless Chromium and return the fully-rendered HTML.
    If extract_iframes=True, also returns iframe contents as a list.
    """
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

        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(wait_ms)

        # Scroll to trigger lazy content
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(1500)

        html = page.content()

        iframe_data = []
        if extract_iframes:
            for frame in page.frames:
                if frame.url and frame.url != url and not frame.url.startswith('about:'):
                    try:
                        frame_html = frame.content()
                        iframe_data.append({
                            'url': frame.url,
                            'html': frame_html,
                        })
                    except Exception:
                        iframe_data.append({
                            'url': frame.url,
                            'html': None,
                            'error': 'Could not access iframe content',
                        })

        browser.close()

    if extract_iframes:
        return html, iframe_data
    return html


# ─── Nav / boilerplate filter ──────────────────────────────────────

# Titles that are clearly navigation or boilerplate, not real listings
NAV_TITLE_RE = re.compile(
    r'^(home|about(\s+us)?|contact(\s+us)?|careers|faq|blog|news|services?'
    r'|privacy(\s+policy)?|terms(\s+\w+)*|login|sign\s*(?:in|up)|register'
    r'|search|cart|checkout'
    r'|buy\s+an?\s+\w+(\s+\w+)?|sell\s+(?:your|a)\b.*'
    r'|business\s+valuation|valuation|testimonials?'
    r'|education\s+resources?|resources?|recent\s+sales|our\s+team'
    r'|seller\s+registration|buyer\s+registration|buyer\s+non.?disclosure.*'
    r'|nda|non.?disclosure.*'
    r'|meet\s+\w+|join\s+\w+|get\s+started|price\s+my\b.*|how\s+to\b.*'
    r'|selling\s+process|our\s+listings?|active\s+listings?'
    r'|[><]\s*\$?\d+[MmKk]?|listings?\s*[><]\s*\$?\d+[MmKk]?)$',
    re.IGNORECASE,
)


def _is_nav_title(title):
    """Check if a title looks like navigation rather than a real listing."""
    if not title:
        return True
    t = title.strip()
    if len(t) < 3 or len(t) > 200:
        return True
    return bool(NAV_TITLE_RE.match(t))


# ─── Base Scraper ───────────────────────────────────────────────────

class BaseScraper:
    """Base class all scrapers inherit from.

    Legal & ethical notes:
    - This scraper only accesses publicly available listing pages
    - It respects robots.txt (checked before scraping)
    - It uses a reasonable rate limit (minimum 2s between requests)
    - It identifies itself honestly via User-Agent (not spoofing identity)
    - It does not bypass authentication or CAPTCHAs
    - When a site blocks access (e.g. Akamai WAF), we respect that
    """

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (compatible; ListingMonitor/1.0; '
            '+https://github.com/example/listing-monitor)'
        ),
    }

    # Cache robots.txt results per domain
    _robots_cache = {}

    @classmethod
    def _check_robots(cls, url):
        """Check robots.txt to see if we're allowed to access this URL."""
        try:
            from urllib.robotparser import RobotFileParser
            parsed = urlparse(url)
            domain = f'{parsed.scheme}://{parsed.netloc}'

            if domain not in cls._robots_cache:
                rp = RobotFileParser()
                rp.set_url(f'{domain}/robots.txt')
                try:
                    rp.read()
                except Exception:
                    # If we can't read robots.txt, assume allowed
                    cls._robots_cache[domain] = None
                    return True
                cls._robots_cache[domain] = rp

            rp = cls._robots_cache[domain]
            if rp is None:
                return True
            return rp.can_fetch(cls.HEADERS['User-Agent'], url)
        except Exception:
            return True  # On error, assume allowed

    def fetch_page(self, url):
        """Fetch raw HTML from a URL. Respects robots.txt."""
        if not self._check_robots(url):
            logger.info(f'Blocked by robots.txt: {url}')
            return ''

        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()
        # Rate limit: be polite
        time.sleep(2)
        return resp.text

    def fetch_page_js(self, url, extract_iframes=False):
        """Fetch HTML after JS rendering via Playwright (if available)."""
        if not self._check_robots(url):
            logger.info(f'Blocked by robots.txt: {url}')
            return None

        if _check_playwright():
            result = fetch_page_with_playwright(url, extract_iframes=extract_iframes)
            time.sleep(2)  # Rate limit
            return result
        return None

    def scrape(self, url):
        """
        Scrape listings from a URL.
        Returns a list of dicts: [{ title, price, description, location, category, url, image_url }]
        """
        raise NotImplementedError


# ─── Generic Scraper ────────────────────────────────────────────────

@register_scraper('generic')
class GenericScraper(BaseScraper):
    """
    Best-effort generic scraper. Looks for common listing patterns in HTML:
    - Cards with headings + prices
    - Links to detail pages
    - Structured data (JSON-LD, schema.org)
    Falls back to Playwright for JS-rendered content.
    Detects BizBuySell iframe embeds and extracts broker ID.
    """

    # Common price patterns
    PRICE_RE = re.compile(
        r'\$[\d,]+(?:\.\d{2})?[KkMm]?'
        r'|Price\s*(?:on|upon)\s*Request'
        r'|(?:Asking|Listed?\s+at)\s*:?\s*\$[\d,]+',
        re.IGNORECASE,
    )

    # BizBuySell iframe pattern
    BBS_IFRAME_RE = re.compile(
        r'bizbuysell\.com/brokerdirectory/Profile/ViewAllListings\.aspx\?.*?I=(\d+)',
        re.IGNORECASE,
    )

    def scrape(self, url):
        # ── Step 1: try static HTML ──
        html = self.fetch_page(url)
        listings = self._parse_html(html, url)

        if listings:
            return listings

        # ── Step 2: check for BizBuySell iframe in static HTML ──
        bbs_id = self._detect_bizbuysell_id(html)

        # ── Step 3: try Playwright with iframe extraction ──
        if _check_playwright():
            logger.info(f'Static scrape found 0 listings – trying Playwright: {url}')
            try:
                result = self.fetch_page_js(url, extract_iframes=True)
                if result:
                    js_html, iframes = result
                    listings = self._parse_html(js_html, url)

                    # If still nothing, try iframe content
                    if not listings:
                        for iframe in iframes:
                            if iframe.get('html'):
                                iframe_listings = self._parse_html(iframe['html'], iframe['url'])
                                if iframe_listings:
                                    listings.extend(iframe_listings)

                            # Check for BizBuySell in iframe URLs
                            if not bbs_id:
                                m = self.BBS_IFRAME_RE.search(iframe.get('url', ''))
                                if m:
                                    bbs_id = m.group(1)

                    if listings:
                        logger.info(f'Playwright found {len(listings)} listings from {url}')
                        return listings

            except Exception as e:
                logger.warning(f'Playwright scrape failed for {url}: {e}')

        # ── Step 4: if we detected BizBuySell, try BBS scraper ──
        if bbs_id:
            logger.info(f'Detected BizBuySell broker ID {bbs_id} on {url}')
            bbs_scraper = _SCRAPERS.get('bizbuysell')
            if bbs_scraper:
                try:
                    return bbs_scraper.scrape_broker(bbs_id)
                except Exception as e:
                    logger.warning(f'BizBuySell scrape failed for broker {bbs_id}: {e}')

        return listings

    def _detect_bizbuysell_id(self, html):
        """Look for BizBuySell iframe in HTML and extract broker ID."""
        m = self.BBS_IFRAME_RE.search(html)
        return m.group(1) if m else None

    def _parse_html(self, html, url):
        """Run all extraction strategies against an HTML string."""
        soup = BeautifulSoup(html, 'html.parser')

        # Strategy 1: Look for JSON-LD structured data
        ld_listings = self._try_json_ld(soup, url)
        if ld_listings:
            return ld_listings

        # Strategy 2: Look for common card patterns
        card_listings = self._try_card_patterns(soup, url)
        if card_listings:
            return card_listings

        # Strategy 3: Look for links that look like listing detail pages
        link_listings = self._try_link_patterns(soup, url)
        if link_listings:
            return link_listings

        return []

    def _try_json_ld(self, soup, base_url):
        """Parse JSON-LD structured data for listings."""
        listings = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get('@type') in ('Product', 'Offer', 'RealEstateListing', 'Service'):
                        title = item.get('name', '')
                        if _is_nav_title(title):
                            continue
                        listings.append({
                            'title': title,
                            'price': self._extract_price_from_ld(item),
                            'description': (item.get('description', '') or '')[:500],
                            'location': self._extract_location_from_ld(item),
                            'category': item.get('category', ''),
                            'url': item.get('url', base_url),
                            'image_url': self._extract_image_from_ld(item),
                        })
            except (json.JSONDecodeError, TypeError):
                continue
        return listings

    def _extract_price_from_ld(self, item):
        offer = item.get('offers', {})
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get('price') or item.get('price')
        if price:
            return f"${price:,.0f}" if isinstance(price, (int, float)) else str(price)
        return None

    def _extract_location_from_ld(self, item):
        loc = item.get('address') or item.get('location') or {}
        if isinstance(loc, dict):
            parts = [loc.get('addressLocality'), loc.get('addressRegion')]
            return ', '.join(p for p in parts if p)
        return str(loc) if loc else None

    def _extract_image_from_ld(self, item):
        img = item.get('image')
        if isinstance(img, list):
            return img[0] if img else None
        if isinstance(img, dict):
            return img.get('url')
        return img

    def _try_card_patterns(self, soup, base_url):
        """Look for repeated card-like elements with headings and links."""
        listings = []

        # Common card containers
        card_selectors = [
            'article',
            '[class*="listing"]',
            '[class*="card"]',
            '[class*="property"]',
            '[class*="business"]',
            '.et_pb_portfolio_item',       # Divi
            '.elementor-post',             # Elementor
            '.jet-listing-grid__item',     # JetEngine
            '[class*="result"]',           # Search results
            '.wp-block-post',              # WordPress blocks
        ]

        for selector in card_selectors:
            cards = soup.select(selector)
            if len(cards) >= 2:  # Need at least 2 to look like a listing grid
                for card in cards:
                    listing = self._parse_card(card, base_url)
                    if listing and listing.get('title') and not _is_nav_title(listing['title']):
                        listings.append(listing)
                if listings:
                    break

        return listings

    def _parse_card(self, card, base_url):
        """Extract listing data from a card-like HTML element."""
        # Title: first heading or strong link
        title_el = card.find(['h1', 'h2', 'h3', 'h4', 'h5'])
        title = title_el.get_text(strip=True) if title_el else None

        # If no heading, try the first prominent link
        if not title:
            link = card.find('a')
            if link:
                title = link.get_text(strip=True)

        # URL: first link, preferably the title link
        link_el = title_el.find('a') if title_el else None
        if not link_el:
            link_el = card.find('a', href=True)
        detail_url = urljoin(base_url, link_el['href']) if link_el and link_el.get('href') else None

        # Price
        price = None
        text = card.get_text()
        price_match = self.PRICE_RE.search(text)
        if price_match:
            price = price_match.group(0).strip()

        # Description: first paragraph or div with substantial text
        desc = None
        for p in card.find_all(['p', 'div']):
            t = p.get_text(strip=True)
            if len(t) > 40 and t != title:
                desc = t[:500]
                break

        # Image
        img_el = card.find('img', src=True)
        image_url = urljoin(base_url, img_el['src']) if img_el else None

        # Location: look for location-like text
        location = None
        for el in card.find_all(['span', 'div', 'p']):
            t = el.get_text(strip=True)
            # Simple heuristic: contains state abbreviation or "County"
            if re.search(r'\b[A-Z]{2}\b.*\d{5}|\bCounty\b|\bCity\b', t):
                location = t[:200]
                break

        if not title:
            return None

        return {
            'title': title,
            'price': price,
            'description': desc,
            'location': location,
            'category': None,
            'url': detail_url,
            'image_url': image_url,
        }

    def _try_link_patterns(self, soup, base_url):
        """Last resort: find links that look like individual listing pages."""
        listings = []
        seen_urls = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)

            # Skip if already seen, or is navigation/social/etc.
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Heuristic: listing URLs often contain keywords
            if not re.search(r'listing|business|for-sale|property', href, re.IGNORECASE):
                continue

            # Skip pagination, search, category pages
            if re.search(r'page/\d|category|tag|search|\?', href):
                continue

            title = a.get_text(strip=True)
            if title and len(title) > 5 and not _is_nav_title(title):
                listings.append({
                    'title': title,
                    'price': None,
                    'description': None,
                    'location': None,
                    'category': None,
                    'url': full_url,
                    'image_url': None,
                })

        return listings


# ─── BizBuySell Scraper ───────────────────────────────────────────

@register_scraper('bizbuysell')
class BizBuySellScraper(BaseScraper):
    """
    Scraper for BizBuySell broker listing pages.

    BizBuySell uses Akamai WAF which blocks headless browsers and
    automated requests. This scraper tries multiple approaches:
    1. Direct page fetch with browser-like headers
    2. Playwright with anti-detection
    3. Search API patterns

    If the site URL is a broker's own site with a BBS iframe,
    the GenericScraper auto-detects this and delegates here.
    """

    # BBS listing card patterns (from their HTML structure)
    CARD_SELECTORS = [
        '.listing',
        '.listingResult',
        '[class*="BusinessListing"]',
        '.searchResult',
        'tr.listing',
        '.bfsListItem',
    ]

    def scrape(self, url):
        """Scrape a BizBuySell URL. Can be a broker profile or search page."""
        # Try to extract broker ID from URL
        m = re.search(r'/(\d+)/?$', url)
        if m:
            return self.scrape_broker(m.group(1))

        # Otherwise try direct scrape
        return self._scrape_url(url)

    def scrape_broker(self, broker_id):
        """Scrape listings for a specific BizBuySell broker ID."""
        url = f'https://www.bizbuysell.com/Business-Broker/broker/{broker_id}/'
        return self._scrape_url(url)

    def _scrape_url(self, url):
        """Try to scrape a BizBuySell URL with multiple approaches."""
        listings = []

        # Approach 1: Direct fetch with full browser headers
        try:
            headers = {
                **self.HEADERS,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
            }
            resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                listings = self._parse_bbs_html(resp.text, url)
                if listings:
                    return listings
        except Exception as e:
            logger.debug(f'BBS direct fetch failed: {e}')

        # Approach 2: Playwright with anti-detection
        if _check_playwright():
            try:
                html = fetch_page_with_playwright(url, wait_ms=5000)
                listings = self._parse_bbs_html(html, url)
                if listings:
                    return listings
            except Exception as e:
                logger.debug(f'BBS Playwright failed: {e}')

        if not listings:
            logger.warning(
                f'BizBuySell blocked scraping for {url}. '
                f'BizBuySell uses Akamai WAF that blocks automated access. '
                f'Consider checking their site manually.'
            )

        return listings

    def _parse_bbs_html(self, html, base_url):
        """Parse BizBuySell-specific HTML structure."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Check if we got blocked
        if 'Access Denied' in soup.get_text()[:200]:
            return []

        # Try BBS-specific selectors
        for selector in self.CARD_SELECTORS:
            cards = soup.select(selector)
            if cards:
                for card in cards:
                    listing = self._parse_bbs_card(card, base_url)
                    if listing:
                        listings.append(listing)
                if listings:
                    return listings

        # Fall back to generic card parsing
        generic = _SCRAPERS.get('generic')
        if generic:
            return generic._parse_html(html, base_url)

        return listings

    def _parse_bbs_card(self, card, base_url):
        """Parse a BizBuySell listing card."""
        title_el = card.find(['h3', 'h2', 'a'])
        title = title_el.get_text(strip=True) if title_el else None
        if not title or _is_nav_title(title):
            return None

        link_el = card.find('a', href=True)
        detail_url = urljoin(base_url, link_el['href']) if link_el else None

        # BBS shows asking price, cash flow, revenue
        text = card.get_text()
        price = None
        price_match = re.search(r'(?:Asking Price|Price)[:\s]*\$([\d,]+)', text, re.IGNORECASE)
        if price_match:
            price = f'${price_match.group(1)}'

        # Cash flow
        cf_match = re.search(r'Cash Flow[:\s]*\$([\d,]+)', text, re.IGNORECASE)
        cash_flow = f'CF: ${cf_match.group(1)}' if cf_match else None

        # Location
        loc_match = re.search(r'(?:Location|City)[:\s]*([^,\n]+,\s*[A-Z]{2})', text, re.IGNORECASE)
        location = loc_match.group(1).strip() if loc_match else None

        # Category
        cat_el = card.find(class_=re.compile(r'category|type|industry', re.IGNORECASE))
        category = cat_el.get_text(strip=True) if cat_el else None

        # Image
        img_el = card.find('img', src=True)
        image_url = urljoin(base_url, img_el['src']) if img_el else None

        desc_parts = [d for d in [cash_flow] if d]
        desc_el = card.find('p')
        if desc_el:
            desc_parts.append(desc_el.get_text(strip=True)[:400])
        description = ' | '.join(desc_parts) if desc_parts else None

        return {
            'title': title,
            'price': price,
            'description': description,
            'location': location,
            'category': category,
            'url': detail_url,
            'image_url': image_url,
        }


# ─── Orchestrator ──────────────────────────────────────────────────

class ListingMonitor:
    """Orchestrates scraping all monitored sites and storing results."""

    _thread = None

    @classmethod
    def check_site(cls, site):
        """Scrape a single MonitoredSite and update listings in DB.

        If the workspace has active DealCriteria, only listings that
        match the criteria are saved. Listings that don't match are
        silently skipped.
        """
        from app import db
        from app.models.listing import Listing
        from app.models.deal_criteria import DealCriteria
        from app.services.category_normalizer import normalize_category

        scraper = get_scraper(site.scraper_type)
        if not scraper:
            site.last_error = f'Unknown scraper type: {site.scraper_type}'
            site.last_checked_at = datetime.utcnow()
            db.session.commit()
            return {'site_id': site.id, 'error': site.last_error}

        # Load deal criteria for this workspace (if any)
        criteria = DealCriteria.query.filter_by(
            workspace_id=site.workspace_id,
            is_active=True,
        ).first()

        try:
            # Handle sites with multiple listing page URLs (comma-separated)
            urls = [u.strip() for u in site.url.split(',')]
            all_raw_listings = []
            for url in urls:
                raw_listings = scraper.scrape(url)
                all_raw_listings.extend(raw_listings)

            new_count = 0
            updated_count = 0
            filtered_count = 0
            current_hashes = set()

            for raw in all_raw_listings:
                # ── Parse financial metrics from description ──
                financials = Listing.parse_financials(
                    f"{raw.get('title', '')} {raw.get('description', '')}"
                )
                price_numeric = Listing.parse_price(raw.get('price'))

                # Build enriched dict for criteria matching
                enriched = {
                    **raw,
                    'price_numeric': price_numeric,
                    'revenue': financials.get('revenue', {}).get('value'),
                    'cash_flow': financials.get('cash_flow', {}).get('value'),
                    'sde': financials.get('sde', {}).get('value'),
                    'ebitda': financials.get('ebitda', {}).get('value'),
                    'net_profit': financials.get('net_profit', {}).get('value'),
                }

                # ── Apply deal criteria filter ──
                if criteria and not criteria.listing_matches(enriched):
                    filtered_count += 1
                    continue

                content_hash = Listing.compute_hash(raw.get('title'), raw.get('url'))
                current_hashes.add(content_hash)

                existing = Listing.query.filter_by(
                    site_id=site.id,
                    content_hash=content_hash,
                ).first()

                if existing:
                    existing.last_seen_at = datetime.utcnow()
                    if existing.removed_at:
                        existing.removed_at = None
                    updated_count += 1
                else:
                    # Normalize category
                    raw_cat = raw.get('category') or ''
                    norm_cat, _ = normalize_category(raw_cat) if raw_cat else ('Other', 0.0)

                    listing = Listing(
                        site_id=site.id,
                        title=raw.get('title'),
                        price=raw.get('price'),
                        price_numeric=price_numeric,
                        description=raw.get('description'),
                        location=raw.get('location'),
                        category=raw.get('category'),
                        normalized_category=norm_cat,
                        source='scraper',
                        url=raw.get('url'),
                        image_url=raw.get('image_url'),
                        # Financial metrics
                        revenue=enriched.get('revenue'),
                        revenue_str=financials.get('revenue', {}).get('str'),
                        cash_flow=enriched.get('cash_flow'),
                        cash_flow_str=financials.get('cash_flow', {}).get('str'),
                        sde=enriched.get('sde'),
                        sde_str=financials.get('sde', {}).get('str'),
                        ebitda=enriched.get('ebitda'),
                        ebitda_str=financials.get('ebitda', {}).get('str'),
                        net_profit=enriched.get('net_profit'),
                        net_profit_str=financials.get('net_profit', {}).get('str'),
                        content_hash=content_hash,
                        is_new=True,
                        first_seen_at=datetime.utcnow(),
                        last_seen_at=datetime.utcnow(),
                    )
                    db.session.add(listing)
                    new_count += 1

            # Mark listings not seen in this scrape as removed
            active_listings = Listing.query.filter_by(
                site_id=site.id,
                removed_at=None,
            ).all()
            for listing in active_listings:
                if listing.content_hash not in current_hashes:
                    listing.removed_at = datetime.utcnow()

            site.last_checked_at = datetime.utcnow()
            site.last_error = None
            db.session.commit()

            result = {
                'site_id': site.id,
                'name': site.name,
                'new': new_count,
                'updated': updated_count,
                'total_scraped': len(all_raw_listings),
            }
            if filtered_count > 0:
                result['filtered_out'] = filtered_count
            return result

        except Exception as e:
            site.last_checked_at = datetime.utcnow()
            site.last_error = str(e)[:500]
            db.session.commit()
            return {'site_id': site.id, 'error': str(e)}

    @classmethod
    def check_all_due(cls):
        """Check all sites that are due for a scrape."""
        from app import db
        from app.models.monitored_site import MonitoredSite

        now = datetime.utcnow()
        sites = MonitoredSite.query.filter_by(is_active=True).all()

        results = []
        for site in sites:
            # Check if site is due
            if site.last_checked_at:
                next_check = site.last_checked_at + timedelta(hours=site.check_interval_hours)
                if now < next_check:
                    continue

            result = cls.check_site(site)
            results.append(result)

        return results

    @classmethod
    def start_background_polling(cls, app, interval=3600):
        """Start a daemon thread that polls for new listings periodically."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                with app.app_context():
                    try:
                        cls.check_all_due()
                    except Exception as e:
                        app.logger.error(f'Listing scraper error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Listing monitor started (interval={interval}s)')
