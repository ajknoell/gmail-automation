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

# --- Owner retirement likelihood detection patterns ---

# Patterns for owner tenure / experience duration
TENURE_PATTERNS = [
    re.compile(r'(\d{1,2})\+?\s*years?\s*(?:of\s+)?(?:experience|in\s+(?:the\s+)?(?:business|industry|trade))', re.IGNORECASE),
    re.compile(r'(?:serving|providing|operating|in\s+business)\s*(?:since|for\s+over|for)\s*(\d{4})', re.IGNORECASE),
    re.compile(r'(?:over|more\s+than)\s*(\d{1,2})\s*(?:decades?|years?)\s*(?:of\s+)?(?:experience|service)', re.IGNORECASE),
    re.compile(r'(?:family[\s-]owned|family\s+business)\s*(?:since|for\s+over|for)\s*(\d{4})', re.IGNORECASE),
]

# Patterns for biographical age indicators
BIO_AGE_PATTERNS = [
    re.compile(r'(?:class\s+of|graduated?\s+(?:in\s+)?|graduated\s+from\s+\w+\s+in\s+)(\d{4})', re.IGNORECASE),
    re.compile(r'(\d{1,2})\s*(?:decades?)\s*(?:of\s+)?(?:experience|service|in)', re.IGNORECASE),
    re.compile(r'(?:retired|semi[\s-]retired|winding\s+down|succession\s+plan|transition\s+plan)', re.IGNORECASE),
]

# Patterns for family business language (general — business is family-related)
FAMILY_BIZ_PATTERNS = [
    re.compile(r'(?:family[\s-]owned|family\s+business|family[\s-]run|family[\s-]operated)', re.IGNORECASE),
    re.compile(r'(?:father|mother|dad)\s+(?:and\s+)?(?:son|daughter)', re.IGNORECASE),
    re.compile(r'(?:passed\s+down|handed\s+down|(?:family|generational)\s+legacy)', re.IGNORECASE),
]

# Patterns that indicate succession already completed — younger owner now runs it
SUCCESSION_COMPLETED_PATTERNS = [
    re.compile(r'(?:second|third|2nd|3rd|next)[\s-]*generation\s*(?:owner|leadership|management)', re.IGNORECASE),
    re.compile(r'(?:son|daughter)\s*(?:now\s+)?(?:runs?|leads?|manages?|owns?|took\s+over|taking\s+over)', re.IGNORECASE),
    re.compile(r'(?:took\s+over|taken\s+over|inherited)\s*(?:the\s+)?(?:business|company|shop|firm)', re.IGNORECASE),
    re.compile(r'(?:new\s+owner|new\s+management|under\s+new\s+(?:ownership|leadership|management))', re.IGNORECASE),
    re.compile(r'(?:recently\s+)?(?:acquired|purchased)\s+(?:by|from)', re.IGNORECASE),
]

# Copyright year pattern for website age detection
COPYRIGHT_YEAR_RE = re.compile(r'(?:\u00a9|&copy;|\(c\)|copyright)\s*(\d{4})', re.IGNORECASE)

# Outdated website indicators (from raw HTML)
OUTDATED_SITE_PATTERNS = [
    re.compile(r'<table[^>]*(?:width|cellpadding|cellspacing|border)=', re.IGNORECASE),
    re.compile(r'<font\s', re.IGNORECASE),
    re.compile(r'<marquee', re.IGNORECASE),
    re.compile(r'<center>', re.IGNORECASE),
]

# Business categories with higher rates of retirement-age owners
HIGH_RETIREMENT_CATEGORIES = {
    'plumber', 'plumbing', 'electrician', 'electrical', 'hvac', 'heating',
    'auto_repair', 'mechanic', 'roofing', 'roofer', 'painting', 'painter',
    'locksmith', 'landscaping', 'landscaper', 'carpet_cleaning', 'dry_cleaner',
    'laundromat', 'barber', 'hair_salon', 'florist', 'bakery', 'deli',
    'hardware_store', 'print_shop', 'tailor', 'upholstery', 'welding',
    'general_contractor', 'masonry', 'concrete', 'fencing', 'pest_control',
    'janitorial', 'cleaning_service', 'moving_company', 'towing',
}

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
            'retirement_score': None,
            'retirement_label': None,
        }

        all_text = ''

        # Step 1: Scrape company website for emails, team size, year founded
        if lead.website:
            website_data = cls.scrape_company_website(lead.website)
            all_text = website_data.get('all_text', '')
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
            elif lead.decision_maker and not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', lead.decision_maker):
                # Clear invalid decision_maker values from prior enrichments
                lead.decision_maker = None

        # Step 2: Google search for LinkedIn company page
        linkedin_data = cls.search_linkedin_company(lead.name, lead.address)
        if linkedin_data.get('url'):
            lead.linkedin_url = linkedin_data['url']
            results['linkedin_url'] = linkedin_data['url']
        if linkedin_data.get('employee_count') and not lead.employee_count:
            lead.employee_count = linkedin_data['employee_count']
            lead.employee_count_source = 'linkedin_google'
            results['employee_count'] = linkedin_data['employee_count']

        # Step 2.5: Owner retirement likelihood detection
        retirement_signals = cls._extract_retirement_signals(all_text, lead)

        # Conditionally search web for owner retirement/succession signals
        has_initial_signals = bool(
            retirement_signals.get('tenure_language')
            or (retirement_signals.get('year_founded_signal')
                and retirement_signals['year_founded_signal']['years_ago'] >= 20)
            or retirement_signals.get('biographical_signals')
        )
        if lead.decision_maker and has_initial_signals:
            web_signals = cls._search_owner_web_signals(lead)
            retirement_signals['web_search_signals'] = web_signals

        retirement_result = cls._heuristic_retirement_score(retirement_signals, lead)
        retirement_signals['analysis'] = retirement_result

        lead.retirement_score = retirement_result['score']
        lead.retirement_label = retirement_result['label']
        results['retirement_score'] = retirement_result['score']
        results['retirement_label'] = retirement_result['label']

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
            'retirement_signals': retirement_signals,
        })
        lead.set_enrichment_data(extra)

        return results

    @classmethod
    def scrape_company_website(cls, website_url):
        """
        Scrape a business website for emails, employee count, year founded,
        and decision-maker info from main page, /about, /contact, /team pages.

        Returns:
            dict with keys: emails, phones, employee_count, year_founded, decision_maker, all_text
        """
        if not website_url:
            return {'emails': [], 'phones': [], 'employee_count': None, 'year_founded': None, 'decision_maker': None, 'all_text': ''}

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
            'all_text': all_text,
        }

    @classmethod
    def _extract_decision_maker(cls, html_text):
        """Try to extract owner/founder/CEO name from page text."""
        # Strip HTML tags first to avoid matching inside tag attributes
        clean_text = re.sub(r'<[^>]+>', ' ', html_text)

        # Common title patterns — require word boundaries to avoid partial matches
        title_group = r'\b(?:CEO|Chief\s*Executive|Founder|Owner|President|Managing\s*Director)\b'
        name_group = r'([A-Z][a-z]{1,15} [A-Z][a-z]{1,15})'
        patterns = [
            re.compile(title_group + r'[,:\s]*(?:&amp;|&|and)?\s*' + name_group),
            re.compile(name_group + r'\s*[,\-\|]\s*' + title_group),
        ]

        for pattern in patterns:
            match = pattern.search(clean_text)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if len(name) > 4 and len(name) < 50 and not re.match(r'(?:The |This |That |All |Our |New |Web )', name):
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
    def _extract_retirement_signals(cls, all_text, lead):
        """Extract retirement likelihood signals from scraped website text and lead metadata."""
        signals = {
            'year_founded_signal': None,
            'tenure_language': [],
            'website_age_indicators': {
                'copyright_year': None,
                'has_social_media': False,
                'outdated_design_signals': [],
            },
            'biographical_signals': [],
            'business_pattern_signals': {
                'is_family_business': False,
                'succession_completed': False,
                'single_owner': False,
                'no_succession_visible': True,
                'high_retirement_category': False,
            },
        }

        current_year = datetime.utcnow().year

        # Strip HTML tags for content-based matching (avoid matching CSS/JS tokens)
        clean_text = re.sub(r'<[^>]+>', ' ', all_text)

        # 1. Year founded signal
        year_str = lead.year_founded
        if year_str:
            try:
                year_val = int(year_str)
                years_ago = current_year - year_val
                weight = 'high' if years_ago >= 35 else ('medium' if years_ago >= 25 else 'low')
                signals['year_founded_signal'] = {
                    'value': year_str, 'years_ago': years_ago, 'weight': weight,
                }
            except ValueError:
                pass

        # 2. Tenure / experience language
        for pattern in TENURE_PATTERNS:
            for match in pattern.finditer(clean_text):
                snippet = clean_text[max(0, match.start() - 30):match.end() + 30].strip()
                signals['tenure_language'].append({
                    'text': match.group(0).strip(),
                    'context': snippet[:100],
                    'source': 'website',
                })
                if len(signals['tenure_language']) >= 5:
                    break
            if len(signals['tenure_language']) >= 5:
                break

        # 3. Website age indicators
        copyright_matches = COPYRIGHT_YEAR_RE.findall(all_text)
        if copyright_matches:
            try:
                latest_copyright = max(int(y) for y in copyright_matches if y.isdigit())
                signals['website_age_indicators']['copyright_year'] = str(latest_copyright)
            except ValueError:
                pass

        social_patterns = ['facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'tiktok.com', 'youtube.com']
        signals['website_age_indicators']['has_social_media'] = any(s in all_text.lower() for s in social_patterns)

        for pattern in OUTDATED_SITE_PATTERNS:
            if pattern.search(all_text):
                # Store a readable label instead of the raw regex
                label = pattern.pattern.split('[')[0].replace('<', '').replace('\\s', ' ').strip()
                signals['website_age_indicators']['outdated_design_signals'].append(label)

        # 4. Biographical signals
        for pattern in BIO_AGE_PATTERNS:
            for match in pattern.finditer(clean_text):
                snippet = clean_text[max(0, match.start() - 40):match.end() + 40].strip()
                entry = {'text': match.group(0).strip(), 'context': snippet[:120]}
                try:
                    grad_year = int(match.group(1))
                    if 1950 <= grad_year <= 2010:
                        approx_age = current_year - grad_year + 22
                        entry['implied_age_range'] = f'{approx_age - 3}-{approx_age + 3}'
                except (ValueError, IndexError):
                    pass
                signals['biographical_signals'].append(entry)
                if len(signals['biographical_signals']) >= 5:
                    break
            if len(signals['biographical_signals']) >= 5:
                break

        # 5. Family business / succession patterns
        for pattern in FAMILY_BIZ_PATTERNS:
            if pattern.search(clean_text):
                signals['business_pattern_signals']['is_family_business'] = True
                break

        # Check if succession already completed (son/daughter took over = younger owner)
        for pattern in SUCCESSION_COMPLETED_PATTERNS:
            if pattern.search(clean_text):
                signals['business_pattern_signals']['succession_completed'] = True
                signals['business_pattern_signals']['no_succession_visible'] = False
                break

        if not signals['business_pattern_signals']['succession_completed']:
            # Require business-context for "transition" to avoid matching generic uses
            if re.search(r'(?:succession|transition\s+(?:plan|of\s+(?:ownership|leadership|management))|ownership\s+transition|next\s+generation|passing\s+the\s+torch)', clean_text, re.IGNORECASE):
                signals['business_pattern_signals']['no_succession_visible'] = False

        # Single owner: decision maker found but no partners or management team mentioned
        # Validate decision_maker looks like a real name (two capitalized words)
        if lead.decision_maker and re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', lead.decision_maker):
            if not re.search(r'(?:partners?|co-(?:founder|owner)|management\s+team|leadership\s+team)', clean_text, re.IGNORECASE):
                signals['business_pattern_signals']['single_owner'] = True

        # Business category match
        if lead.business_category:
            cat_lower = lead.business_category.lower().replace(' ', '_')
            if any(term in cat_lower for term in HIGH_RETIREMENT_CATEGORIES):
                signals['business_pattern_signals']['high_retirement_category'] = True

        return signals

    @classmethod
    def _search_owner_web_signals(cls, lead):
        """Conditionally search web for owner retirement/succession signals via Tavily."""
        try:
            from app.models.settings import Settings
            from app.services.web_search import WebSearchService

            tavily_key = Settings.get('tavily_api_key')
            if not tavily_key or not lead.decision_maker:
                return {'query': None, 'findings': []}

            owner_name = lead.decision_maker
            company = lead.name
            query = f'"{owner_name}" "{company}" retirement OR succession OR "years of experience" OR retiring'

            web_search = WebSearchService(tavily_key)
            result = web_search.search(query, max_results=3, search_depth='basic', include_answer=True)

            findings = []
            if result.get('answer'):
                findings.append({
                    'text': result['answer'][:300],
                    'url': None,
                    'relevance': 'summary',
                })
            for r in result.get('results', []):
                content = r.get('content', '')
                if content:
                    findings.append({
                        'text': content[:300],
                        'url': r.get('url', ''),
                        'relevance': 'search_result',
                    })

            return {'query': query, 'findings': findings}

        except Exception as e:
            logger.warning(f'Retirement web search failed for "{lead.name}": {e}')
            return {'query': None, 'findings': []}

    @classmethod
    def _heuristic_retirement_score(cls, signals, lead):
        """Score retirement likelihood using heuristic rules. Returns dict with score, label, key_evidence."""
        points = 0
        evidence = []
        current_year = datetime.utcnow().year

        # Year founded
        yf = signals.get('year_founded_signal')
        if yf:
            if yf['years_ago'] >= 35:
                points += 30
                evidence.append(f"Business founded {yf['years_ago']} years ago ({yf['value']})")
            elif yf['years_ago'] >= 25:
                points += 15
                evidence.append(f"Business founded {yf['years_ago']} years ago ({yf['value']})")

        # Tenure language
        tenure = signals.get('tenure_language', [])
        if tenure:
            points += 20
            evidence.append(f"Tenure language: \"{tenure[0]['text']}\"")

        # Biographical signals
        bio = signals.get('biographical_signals', [])
        if bio:
            points += 15
            evidence.append(f"Bio signal: \"{bio[0]['text']}\"")

        # Website age indicators
        wa = signals.get('website_age_indicators', {})
        if wa.get('copyright_year'):
            try:
                years_stale = current_year - int(wa['copyright_year'])
                if years_stale >= 3:
                    points += 10
                    evidence.append(f"Website copyright {years_stale} years stale ({wa['copyright_year']})")
            except ValueError:
                pass
        if not wa.get('has_social_media'):
            points += 5
        if wa.get('outdated_design_signals'):
            points += 5
            evidence.append('Outdated website design detected')

        # Business patterns
        bp = signals.get('business_pattern_signals', {})
        if bp.get('succession_completed'):
            # Son/daughter already took over — current owner is likely younger
            points -= 25
            evidence.append('Succession already completed (younger owner likely)')
        elif bp.get('is_family_business'):
            points += 10
            evidence.append('Family-owned business (original generation)')
        if bp.get('single_owner') and bp.get('no_succession_visible'):
            points += 10
            evidence.append('Single owner, no succession plan visible')
        if bp.get('high_retirement_category'):
            points += 5
            evidence.append('Industry with high retirement-age owner rate')

        # Web search signals (if Tavily ran)
        ws = signals.get('web_search_signals', {})
        if ws.get('findings'):
            points += 15
            evidence.append('Web search found retirement/succession mentions')

        score = max(0, min(points, 100))
        if score >= 75:
            label = 'high'
        elif score >= 40:
            label = 'medium'
        elif score >= 1:
            label = 'low'
        else:
            label = 'unknown'

        return {
            'score': score,
            'label': label,
            'key_evidence': evidence[:5],
        }

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

        if lead.retirement_score and lead.retirement_score >= 60:
            score += 10
            breakdown['retirement_likelihood'] = 10
        elif lead.retirement_score and lead.retirement_score >= 40:
            score += 5
            breakdown['retirement_likelihood'] = 5

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
