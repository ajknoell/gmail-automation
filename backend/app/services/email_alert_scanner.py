"""
Email Alert Scanner
--------------------
Scans Gmail inbox for broker listing alert emails (BizBuySell saved searches,
broker newsletters, etc.) and automatically ingests new listings.

This bypasses BizBuySell's Akamai WAF by reading the listing data directly
from their saved search alert emails instead of scraping the website.
"""

import re
import base64
import logging
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ─── BizBuySell Email Parser ─────────────────────────────────────

class BizBuySellEmailParser:
    """Parse BizBuySell saved search alert emails.

    BizBuySell alert emails typically contain:
    - Multiple listing cards with title, price, location, cash flow, link
    - Subject lines like "New Listings: [Search Name]" or "BizBuySell Saved Search"
    - Sender: noreply@bizbuysell.com or similar
    """

    # Patterns for BizBuySell listing cards in email HTML
    PRICE_RE = re.compile(r'\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?')
    CF_RE = re.compile(r'Cash\s*Flow\s*[:\s]*\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?', re.IGNORECASE)
    REV_RE = re.compile(r'(?:Gross\s*)?Revenue\s*[:\s]*\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?', re.IGNORECASE)
    LOC_RE = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})')

    @classmethod
    def is_bizbuysell_email(cls, from_addr, subject):
        """Check if an email is from BizBuySell."""
        from_lower = (from_addr or '').lower()
        subject_lower = (subject or '').lower()
        return (
            'bizbuysell' in from_lower
            or 'bizbuysell' in subject_lower
            or '@bizbuysell.com' in from_lower
        )

    @classmethod
    def parse_email(cls, html_body, plain_body=None):
        """Parse a BizBuySell alert email and extract listings.

        Returns a list of dicts: [{ title, price, location, url, description, category }]
        """
        if not html_body and not plain_body:
            return []

        # Try HTML parsing first (BBS emails are HTML)
        if html_body:
            listings = cls._parse_html(html_body)
            if listings:
                return listings

        # Fall back to plain text
        if plain_body:
            listings = cls._parse_plain(plain_body)
            if listings:
                return listings

        return []

    @classmethod
    def _parse_html(cls, html):
        """Parse BizBuySell HTML email for listing cards."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # BizBuySell emails use table-based layout with listing links
        # Look for links to bizbuysell.com listing pages
        listing_links = soup.find_all('a', href=re.compile(
            r'bizbuysell\.com.*(?:/Business-Opportunity|/Business/|/listing)', re.IGNORECASE
        ))

        # Also check for links with listing-like paths
        if not listing_links:
            listing_links = soup.find_all('a', href=re.compile(
                r'bizbuysell\.com/Business', re.IGNORECASE
            ))

        seen_urls = set()
        for link in listing_links:
            href = link.get('href', '')
            # Skip duplicate URLs, navigation links, and generic pages
            if href in seen_urls:
                continue
            if re.search(r'(unsubscribe|preferences|saved.?search|login|register)', href, re.IGNORECASE):
                continue

            seen_urls.add(href)

            # Get the listing title from the link text or parent context
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                # Try parent elements
                parent = link.parent
                if parent:
                    title = parent.get_text(strip=True)[:200]

            if not title or len(title) < 5:
                continue

            # Skip navigation-like text
            if re.match(r'^(view\s+all|see\s+more|click\s+here|learn\s+more|view\s+listing)', title, re.IGNORECASE):
                continue

            # Get surrounding text for financial data
            context = cls._get_context_text(link)

            # Extract price
            price = None
            price_match = re.search(r'(?:Asking\s+)?Price\s*[:\s]*(\$[\d,]+)', context, re.IGNORECASE)
            if price_match:
                price = price_match.group(1)
            else:
                # First dollar amount
                price_match = cls.PRICE_RE.search(context)
                if price_match:
                    price = price_match.group(0)

            # Extract cash flow
            cf_match = cls.CF_RE.search(context)
            cash_flow_str = cf_match.group(0) if cf_match else None

            # Extract revenue
            rev_match = cls.REV_RE.search(context)
            revenue_str = rev_match.group(0) if rev_match else None

            # Extract location
            location = None
            loc_match = cls.LOC_RE.search(context)
            if loc_match:
                location = loc_match.group(1)

            # Build description from financial info
            desc_parts = []
            if cash_flow_str:
                desc_parts.append(cash_flow_str)
            if revenue_str:
                desc_parts.append(revenue_str)
            description = ' | '.join(desc_parts) if desc_parts else None

            listings.append({
                'title': title[:500],
                'price': price,
                'location': location,
                'category': None,
                'url': href,
                'description': description,
                'image_url': None,
            })

        return listings

    @classmethod
    def _parse_plain(cls, text):
        """Parse plain text email for listings (fallback)."""
        listings = []

        # Look for BizBuySell URL patterns with surrounding context
        url_pattern = re.compile(r'(https?://\S*bizbuysell\.com\S*)', re.IGNORECASE)

        for match in url_pattern.finditer(text):
            url = match.group(1).rstrip('.,;:)')
            if re.search(r'(unsubscribe|preferences|login)', url, re.IGNORECASE):
                continue

            # Get context: 200 chars before the URL
            start = max(0, match.start() - 200)
            context = text[start:match.end()]

            # Try to extract title from context (line before URL)
            lines = context.split('\n')
            title = None
            for line in reversed(lines[:-1]):
                line = line.strip()
                if len(line) > 10 and not line.startswith('http'):
                    title = line[:200]
                    break

            if not title:
                continue

            price_match = cls.PRICE_RE.search(context)
            price = price_match.group(0) if price_match else None

            loc_match = cls.LOC_RE.search(context)
            location = loc_match.group(1) if loc_match else None

            listings.append({
                'title': title,
                'price': price,
                'location': location,
                'category': None,
                'url': url,
                'description': None,
                'image_url': None,
            })

        return listings

    @classmethod
    def _get_context_text(cls, element):
        """Get text from the element and its parent/sibling context."""
        texts = [element.get_text()]

        # Walk up to find a container (td, div, tr)
        parent = element.parent
        for _ in range(5):
            if parent and parent.name in ('td', 'div', 'tr', 'table', 'li'):
                texts.append(parent.get_text())
                break
            if parent:
                parent = parent.parent

        return ' '.join(texts)


# ─── Generic Broker Email Parser ─────────────────────────────────

class GenericBrokerEmailParser:
    """Parse generic broker listing alert emails.

    Handles common formats like:
    - "New Listing: Title - $Price"
    - Emails with multiple listing cards/sections
    """

    @classmethod
    def parse_email(cls, subject, html_body, plain_body=None):
        """Parse a generic broker email for listing data.

        Returns a list of dicts or a single-element list if the email
        is about one listing.
        """
        from app.services.email_listing_parser import parse_listing_from_email

        body_text = plain_body or ''
        if html_body and not body_text:
            soup = BeautifulSoup(html_body, 'html.parser')
            body_text = soup.get_text('\n', strip=True)

        parsed = parse_listing_from_email(subject, body_text)
        if parsed.get('title'):
            return [parsed]

        return []


# ─── Email Alert Scanner ─────────────────────────────────────────

class EmailAlertScanner:
    """Scans Gmail for broker listing alert emails and ingests them."""

    # Senders and subjects we look for
    ALERT_QUERIES = [
        'from:bizbuysell.com',
        'from:noreply@bizbuysell.com',
        'subject:"saved search" from:bizbuysell',
        'subject:"new listing" from:bizbuysell',
    ]

    @classmethod
    def scan_inbox(cls, workspace_id, days_back=7, custom_query=None):
        """Scan Gmail inbox for broker alert emails and ingest listings.

        Args:
            workspace_id: The workspace to save listings under
            days_back: How many days back to search
            custom_query: Optional custom Gmail search query

        Returns:
            dict with counts: { emails_found, listings_ingested, duplicates_skipped, errors }
        """
        from app import db
        from app.models import OAuthToken
        from app.models.monitored_site import MonitoredSite
        from app.models.listing import Listing
        from app.services.gmail_service import GmailService
        from app.services.category_normalizer import normalize_category

        # Get Gmail connection
        gmail = GmailService()
        if not gmail.connect():
            return {'error': 'Gmail not connected. Please connect your Gmail account first.'}

        # Build search query
        after_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y/%m/%d')

        if custom_query:
            query = f'{custom_query} after:{after_date}'
        else:
            # Combine all alert queries with OR
            query_parts = ' OR '.join(f'({q})' for q in cls.ALERT_QUERIES)
            query = f'({query_parts}) after:{after_date}'

        logger.info(f'Scanning Gmail with query: {query}')

        # Search for emails
        try:
            results = gmail.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50,
            ).execute()
        except Exception as e:
            logger.error(f'Gmail search failed: {e}')
            return {'error': f'Gmail search failed: {str(e)}'}

        messages = results.get('messages', [])
        if not messages:
            return {
                'emails_found': 0,
                'listings_ingested': 0,
                'duplicates_skipped': 0,
                'errors': 0,
                'query_used': query,
            }

        # Find or create an email-ingestion site
        email_site = MonitoredSite.query.filter_by(
            workspace_id=workspace_id,
            scraper_type='email',
        ).first()

        if not email_site:
            email_site = MonitoredSite(
                workspace_id=workspace_id,
                name='Email Ingestion',
                url='email://',
                scraper_type='email',
                is_active=False,
                check_interval_hours=9999,
            )
            db.session.add(email_site)
            db.session.flush()

        emails_found = len(messages)
        listings_ingested = 0
        duplicates_skipped = 0
        errors = 0
        all_listings = []

        # Process each email
        for msg_ref in messages:
            try:
                msg = gmail.service.users().messages().get(
                    userId='me',
                    id=msg_ref['id'],
                    format='full',
                ).execute()

                # Extract headers
                headers = {
                    h['name'].lower(): h['value']
                    for h in msg.get('payload', {}).get('headers', [])
                }
                from_addr = headers.get('from', '')
                subject = headers.get('subject', '')

                # Extract body
                html_body, plain_body = cls._extract_bodies(msg)

                # Route to appropriate parser
                parsed_listings = []

                if BizBuySellEmailParser.is_bizbuysell_email(from_addr, subject):
                    parsed_listings = BizBuySellEmailParser.parse_email(html_body, plain_body)
                else:
                    parsed_listings = GenericBrokerEmailParser.parse_email(
                        subject, html_body, plain_body
                    )

                # Save each parsed listing
                for raw in parsed_listings:
                    try:
                        title = raw.get('title', '').strip()
                        if not title:
                            continue

                        # Check duplicate
                        content_hash = Listing.compute_hash(title, raw.get('url'))
                        existing = Listing.query.filter_by(
                            site_id=email_site.id,
                            content_hash=content_hash,
                        ).first()

                        if existing:
                            duplicates_skipped += 1
                            continue

                        # Parse financials
                        desc_text = f"{title} {raw.get('description', '')}"
                        financials = Listing.parse_financials(desc_text)
                        price_numeric = Listing.parse_price(raw.get('price'))

                        # Normalize category
                        raw_cat = raw.get('category') or ''
                        norm_cat, _ = normalize_category(raw_cat) if raw_cat else ('Other', 0.0)

                        listing = Listing(
                            site_id=email_site.id,
                            title=title,
                            price=raw.get('price'),
                            price_numeric=price_numeric,
                            description=raw.get('description'),
                            location=raw.get('location'),
                            category=raw.get('category'),
                            normalized_category=norm_cat,
                            source='email',
                            url=raw.get('url'),
                            image_url=raw.get('image_url'),
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
                        listings_ingested += 1
                        all_listings.append(raw)

                    except Exception as e:
                        logger.warning(f'Failed to save listing from email: {e}')
                        errors += 1

                # Rate limit
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f'Failed to process email {msg_ref["id"]}: {e}')
                errors += 1

        # Commit all at once
        if listings_ingested > 0:
            email_site.last_checked_at = datetime.utcnow()
            db.session.commit()

        return {
            'emails_found': emails_found,
            'listings_ingested': listings_ingested,
            'duplicates_skipped': duplicates_skipped,
            'errors': errors,
            'query_used': query,
        }

    @classmethod
    def _extract_bodies(cls, message):
        """Extract HTML and plain text bodies from a Gmail message."""
        payload = message.get('payload', {})
        html_body = None
        plain_body = None

        def _walk_parts(parts):
            nonlocal html_body, plain_body
            for part in parts:
                mime_type = part.get('mimeType', '')
                data = part.get('body', {}).get('data')

                if data:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                    if mime_type == 'text/html' and not html_body:
                        html_body = decoded
                    elif mime_type == 'text/plain' and not plain_body:
                        plain_body = decoded

                if part.get('parts'):
                    _walk_parts(part['parts'])

        # Single-part
        if payload.get('body', {}).get('data'):
            decoded = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='replace')
            mime_type = payload.get('mimeType', '')
            if mime_type == 'text/html':
                html_body = decoded
            else:
                plain_body = decoded

        # Multi-part
        if payload.get('parts'):
            _walk_parts(payload['parts'])

        return html_body, plain_body
