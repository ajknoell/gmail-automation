"""
Lead Enrichment Service — scrapes company websites and Google search results
to gather employee count, LinkedIn URL, emails, and other business data.
Uses only free methods: website scraping + Google search snippets.
"""
import re
import time
import logging
import threading
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests

logger = logging.getLogger(__name__)

# Reuse from prospect_discovery
FREE_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'mail.com', 'protonmail.com', 'zoho.com', 'yandex.com',
    'live.com', 'msn.com', 'comcast.net', 'verizon.net', 'att.net',
    'me.com', 'mac.com', 'gmx.com', 'inbox.com',
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})')

# Patterns for employee count on websites
EMPLOYEE_PATTERNS = [
    re.compile(r'(\d{1,6})\+?\s*(?:employees?|team\s*members?|staff|people)', re.IGNORECASE),
    re.compile(r'team\s*of\s*(\d{1,6})', re.IGNORECASE),
    re.compile(r'(?:over|more\s*than|approximately|about|nearly)\s*(\d{1,6})\s*(?:employees?|team|staff|people)', re.IGNORECASE),
    re.compile(r'(\d{1,6})\s*(?:\+\s*)?(?:strong|person|member)\s*team', re.IGNORECASE),
]

# Patterns for founding year
YEAR_PATTERNS = [
    re.compile(r'(?:founded|established|since|started|est\.?)\s*(?:in\s*)?(\d{4})', re.IGNORECASE),
    re.compile(r'(?:since|est\.?)\s*(\d{4})', re.IGNORECASE),
]

# Google search snippet patterns for LinkedIn employee data
LINKEDIN_EMPLOYEE_PATTERNS = [
    re.compile(r'(\d{1,3}(?:,\d{3})*)\s*(?:employees?|followers)', re.IGNORECASE),
    re.compile(r'(\d+)-(\d+)\s*employees?', re.IGNORECASE),
    re.compile(r'Company size\s*[:\s]*(\d+)', re.IGNORECASE),
]

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

# Rate limit between requests
_REQUEST_DELAY = 1.5


class EnrichmentService:
    """Enriches business leads with employee count, LinkedIn URL, emails, and more."""

    @classmethod
    def enrich_lead(cls, lead):
        """
        Full enrichment pipeline for a single lead.

        Modifies the lead object in place with enriched data.
        Returns dict with enrichment results summary.
        """
        results = {
            'emails_found': 0,
            'employee_count': None,
            'linkedin_url': None,
            'year_founded': None,
            'decision_maker': None,
        }

        # Step 1: Scrape company website for emails, team size, year founded
        if lead.website:
            website_data = cls.scrape_company_website(lead.website)
            if website_data['emails']:
                lead.set_emails_found(website_data['emails'])
                results['emails_found'] = len(website_data['emails'])
            if website_data['employee_count']:
                lead.employee_count = website_data['employee_count']
                lead.employee_count_source = 'website'
                results['employee_count'] = website_data['employee_count']
            if website_data['year_founded']:
                lead.year_founded = website_data['year_founded']
                results['year_founded'] = website_data['year_founded']
            if website_data['phones'] and not lead.phone:
                lead.phone = website_data['phones'][0]
            if website_data.get('decision_maker'):
                lead.decision_maker = website_data['decision_maker']
                results['decision_maker'] = website_data['decision_maker']

        # Step 2: Google search for LinkedIn company page
        linkedin_data = cls.search_linkedin_company(lead.name, lead.address)
        if linkedin_data.get('url'):
            lead.linkedin_url = linkedin_data['url']
            results['linkedin_url'] = linkedin_data['url']
        if linkedin_data.get('employee_count') and not lead.employee_count:
            lead.employee_count = linkedin_data['employee_count']
            lead.employee_count_source = 'linkedin_google'
            results['employee_count'] = linkedin_data['employee_count']

        # Step 3: Calculate lead score
        score, breakdown = cls.calculate_score(lead)
        lead.score = score
        lead.set_score_breakdown(breakdown)

        # Update status
        lead.enriched_at = datetime.utcnow()
        lead.status = 'enriched'

        # Auto-qualify if score is high enough
        if score >= 60:
            lead.status = 'qualified'

        # Store extra enrichment data
        extra = lead.get_enrichment_data()
        extra.update({
            'enrichment_timestamp': datetime.utcnow().isoformat(),
            'website_scraped': bool(lead.website),
            'linkedin_searched': True,
        })
        lead.set_enrichment_data(extra)

        return results

    @classmethod
    def scrape_company_website(cls, website_url):
        """
        Scrape a business website for emails, employee count, year founded,
        and decision-maker info from main page, /about, /contact, /team pages.

        Returns:
            dict with keys: emails, phones, employee_count, year_founded, decision_maker
        """
        if not website_url:
            return {'emails': [], 'phones': [], 'employee_count': None, 'year_founded': None, 'decision_maker': None}

        if not website_url.startswith('http'):
            website_url = f'https://{website_url}'

        parsed = urlparse(website_url)
        base = f'{parsed.scheme}://{parsed.netloc}'

        pages_to_check = [
            website_url,
            urljoin(base, '/about'),
            urljoin(base, '/about-us'),
            urljoin(base, '/contact'),
            urljoin(base, '/contact-us'),
            urljoin(base, '/team'),
            urljoin(base, '/our-team'),
        ]

        all_emails = set()
        all_phones = set()
        employee_count = None
        year_founded = None
        decision_maker = None
        all_text = ''

        for url in pages_to_check:
            try:
                resp = requests.get(url, timeout=8, headers=_HEADERS, allow_redirects=True)
                if resp.status_code != 200:
                    continue

                text = resp.text
                all_text += ' ' + text

                # Extract emails
                for email in EMAIL_RE.findall(text):
                    domain = email.split('@')[1].lower()
                    # Filter out free email providers and image/file extensions
                    if domain not in FREE_EMAIL_DOMAINS and not email.endswith(('.png', '.jpg', '.gif', '.svg', '.css', '.js')):
                        all_emails.add(email.lower())

                # Extract phones
                for phone in PHONE_RE.findall(text):
                    all_phones.add(phone)

                # Extract employee count
                if not employee_count:
                    for pattern in EMPLOYEE_PATTERNS:
                        match = pattern.search(text)
                        if match:
                            try:
                                count = int(match.group(1).replace(',', ''))
                                if 1 <= count <= 500000:
                                    employee_count = count
                                    break
                            except (ValueError, IndexError):
                                pass

                # Extract year founded
                if not year_founded:
                    for pattern in YEAR_PATTERNS:
                        match = pattern.search(text)
                        if match:
                            year = match.group(1)
                            if 1800 <= int(year) <= datetime.utcnow().year:
                                year_founded = year
                                break

                time.sleep(_REQUEST_DELAY)
            except Exception:
                continue

        # Try to find decision-maker from team/about pages
        decision_maker = cls._extract_decision_maker(all_text)

        return {
            'emails': sorted(list(all_emails))[:10],
            'phones': sorted(list(all_phones))[:5],
            'employee_count': employee_count,
            'year_founded': year_founded,
            'decision_maker': decision_maker,
        }

    @classmethod
    def _extract_decision_maker(cls, html_text):
        """Try to extract owner/founder/CEO name from page text."""
        # Common title patterns
        patterns = [
            re.compile(r'(?:CEO|Chief\s*Executive|Founder|Owner|President|Managing\s*Director)[,:\s]*(?:&amp;|&|and)?\s*([A-Z][a-z]+ [A-Z][a-z]+)', re.IGNORECASE),
            re.compile(r'([A-Z][a-z]+ [A-Z][a-z]+)\s*[,\-\|]\s*(?:CEO|Chief\s*Executive|Founder|Owner|President|Managing\s*Director)', re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(html_text)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if len(name) > 4 and len(name) < 50:
                    return name

        return None

    @classmethod
    def search_linkedin_company(cls, company_name, address=None):
        """
        Search Google for the company's LinkedIn page.
        Extract employee count from the Google snippet if available.

        Returns:
            dict with keys: url, employee_count
        """
        result = {'url': None, 'employee_count': None}

        if not company_name:
            return result

        # Build search query
        location_hint = ''
        if address:
            # Extract city from address (usually the format "123 Main St, City, State")
            parts = [p.strip() for p in address.split(',')]
            if len(parts) >= 2:
                location_hint = parts[-2] if len(parts) >= 3 else parts[-1]

        query = f'{company_name} {location_hint} site:linkedin.com/company'.strip()

        try:
            # Use Google search to find LinkedIn page
            resp = requests.get(
                'https://www.google.com/search',
                params={'q': query, 'num': 3},
                headers={
                    **_HEADERS,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                },
                timeout=10,
            )

            if resp.status_code == 200:
                text = resp.text

                # Extract LinkedIn company URL from results
                linkedin_pattern = re.compile(
                    r'https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9_-]+/?',
                )
                matches = linkedin_pattern.findall(text)
                if matches:
                    result['url'] = matches[0].rstrip('/')

                # Try to extract employee count from snippet
                for pattern in LINKEDIN_EMPLOYEE_PATTERNS:
                    match = pattern.search(text)
                    if match:
                        try:
                            if match.lastindex and match.lastindex >= 2:
                                # Range like "11-50 employees" → take midpoint
                                low = int(match.group(1).replace(',', ''))
                                high = int(match.group(2).replace(',', ''))
                                result['employee_count'] = (low + high) // 2
                            else:
                                count = int(match.group(1).replace(',', ''))
                                if 1 <= count <= 500000:
                                    result['employee_count'] = count
                            break
                        except (ValueError, IndexError):
                            pass

            time.sleep(_REQUEST_DELAY)

        except Exception as e:
            logger.warning(f'LinkedIn search failed for "{company_name}": {e}')

        return result

    @classmethod
    def calculate_score(cls, lead):
        """
        Calculate a lead quality score (0-100) based on available data.

        Scoring factors:
        - Has website: +15
        - Has phone: +10
        - Has email: +20
        - Has employee count: +10
        - Employee count in sweet spot (5-200): +10
        - Google rating >= 4.0: +10
        - Review count >= 10: +10
        - Has LinkedIn: +10
        - Has decision-maker: +5

        Returns:
            (score: int, breakdown: dict)
        """
        score = 0
        breakdown = {}

        if lead.website:
            score += 15
            breakdown['website'] = 15

        if lead.phone:
            score += 10
            breakdown['phone'] = 10

        emails = lead.get_emails_found()
        if emails:
            score += 20
            breakdown['email'] = 20

        if lead.employee_count:
            score += 10
            breakdown['employee_count_known'] = 10
            if 5 <= lead.employee_count <= 200:
                score += 10
                breakdown['employee_count_sweet_spot'] = 10

        if lead.google_rating and lead.google_rating >= 4.0:
            score += 10
            breakdown['high_rating'] = 10

        if lead.review_count and lead.review_count >= 10:
            score += 10
            breakdown['review_count'] = 10

        if lead.linkedin_url:
            score += 10
            breakdown['linkedin'] = 10

        if lead.decision_maker:
            score += 5
            breakdown['decision_maker'] = 5

        return min(score, 100), breakdown


class EnrichmentWorker:
    """Background worker that auto-enriches new leads."""
    _thread = None

    @classmethod
    def enrich_pending_leads(cls, app):
        """Find and enrich all leads with status 'new'."""
        with app.app_context():
            from app import db
            from app.models.lead import Lead

            leads = Lead.query.filter_by(status='new').order_by(Lead.created_at.asc()).limit(10).all()

            if not leads:
                return 0

            enriched = 0
            for lead in leads:
                try:
                    lead.status = 'enriching'
                    db.session.commit()

                    EnrichmentService.enrich_lead(lead)
                    db.session.commit()
                    enriched += 1

                    logger.info(f'Enriched lead "{lead.name}" — score={lead.score}, employees={lead.employee_count}')
                except Exception as e:
                    logger.error(f'Failed to enrich lead "{lead.name}": {e}')
                    lead.status = 'enriched'  # Move forward even on partial failure
                    db.session.commit()

                # Rate limit between leads
                time.sleep(3)

            return enriched

    @classmethod
    def start_background_polling(cls, app, interval=600):
        """Start a daemon thread that polls for new leads to enrich."""
        if cls._thread is not None:
            return

        def poll_loop():
            while True:
                time.sleep(interval)
                try:
                    count = cls.enrich_pending_leads(app)
                    if count:
                        app.logger.info(f'Enrichment worker: enriched {count} leads')
                except Exception as e:
                    app.logger.error(f'Enrichment worker error: {e}')

        cls._thread = threading.Thread(target=poll_loop, daemon=True)
        cls._thread.start()
        app.logger.info(f'Enrichment worker started (interval={interval}s)')
