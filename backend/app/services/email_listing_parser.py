"""
Email Listing Parser
---------------------
Extracts business listing details from broker email text.

Broker emails typically follow patterns like:
- "New Listing: Pizza Restaurant in Bergen County, NJ - $450,000"
- Sections with "Asking Price:", "Revenue:", "Cash Flow:", "Location:", etc.
- Links to the listing detail page on the broker's site
"""

import re
from urllib.parse import urlparse


def parse_listing_from_email(subject, body):
    """
    Parse a broker email and extract listing details.

    Returns a dict with:
        title, price, description, location, category, url
    """
    full_text = f"{subject}\n{body}"

    result = {
        'title': _extract_title(subject, body),
        'price': _extract_price(full_text),
        'description': _extract_description(body),
        'location': _extract_location(full_text),
        'category': _extract_category(full_text),
        'url': _extract_url(body),
    }

    return result


def _extract_title(subject, body):
    """Extract the listing title.

    Priority:
    1. "New Listing: <title>" pattern in subject
    2. "Business for Sale: <title>" in subject
    3. Subject line itself (cleaned up)
    4. First heading-like line in body
    """
    # Try subject patterns
    for pattern in [
        r'(?:new\s+)?listing\s*[:\-–]\s*(.+?)(?:\s*[-–|]\s*\$|\s*$)',
        r'business\s+for\s+sale\s*[:\-–]\s*(.+?)(?:\s*[-–|]\s*\$|\s*$)',
        r'just\s+listed\s*[:\-–]\s*(.+?)(?:\s*[-–|]\s*\$|\s*$)',
        r'new\s+opportunity\s*[:\-–]\s*(.+?)(?:\s*[-–|]\s*\$|\s*$)',
    ]:
        m = re.search(pattern, subject, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            if len(title) > 5:
                return title

    # Try body patterns
    for pattern in [
        r'(?:business|listing)\s+(?:name|title)\s*[:\-]\s*(.+)',
        r'(?:^|\n)\s*([A-Z][^\n]{10,60}(?:for\s+sale|business|restaurant|shop|store)[^\n]*)',
    ]:
        m = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
        if m:
            title = m.group(1).strip()
            if len(title) > 5:
                return title

    # Fall back to cleaned subject
    if subject:
        # Remove common prefixes
        cleaned = re.sub(
            r'^(re:\s*|fw:\s*|fwd:\s*|new listing\s*[-:–]\s*|just listed\s*[-:–]\s*)',
            '', subject, flags=re.IGNORECASE,
        ).strip()
        if len(cleaned) > 5:
            return cleaned

    return None


def _extract_price(text):
    """Extract asking price from text."""
    # Look for labeled price first
    for pattern in [
        r'(?:asking\s+)?price\s*[:\-]\s*(\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?)',
        r'listed?\s+(?:at|for)\s*[:\-]?\s*(\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?)',
        r'(\$[\d,]+(?:\.\d{2})?(?:\s*[KkMm])?)\s*(?:asking|list)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Look for standalone price (first prominent dollar amount)
    m = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)\s*([KkMm])?', text)
    if m:
        raw = m.group(0).strip()
        # Verify it's a reasonable business price (> $10K)
        val = float(m.group(1).replace(',', ''))
        suffix = (m.group(2) or '').upper()
        if suffix == 'K':
            val *= 1000
        elif suffix == 'M':
            val *= 1_000_000
        if val >= 10_000:
            return raw

    return None


def _extract_description(body):
    """Extract a description from the email body."""
    # Remove URLs and email artifacts
    cleaned = re.sub(r'https?://\S+', '', body)
    cleaned = re.sub(r'\[.*?\]', '', cleaned)
    cleaned = re.sub(r'<.*?>', '', cleaned)

    # Look for description section
    for pattern in [
        r'description\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z]|\n\s*(?:price|asking|revenue|cash|location|category|contact|call|email|visit))',
        r'(?:about\s+(?:this|the)\s+(?:business|listing))\s*[:\-]?\s*(.+?)(?:\n\n|\n[A-Z])',
        r'(?:opportunity|details?)\s*[:\-]\s*(.+?)(?:\n\n|\n[A-Z])',
    ]:
        m = re.search(pattern, cleaned, re.IGNORECASE | re.DOTALL)
        if m:
            desc = m.group(1).strip()
            if len(desc) > 20:
                return desc[:500]

    # Fall back: grab the longest paragraph
    paragraphs = re.split(r'\n\s*\n', cleaned)
    best = ''
    for p in paragraphs:
        p = p.strip()
        # Skip short paragraphs, signatures, disclaimers
        if len(p) < 30:
            continue
        if re.match(r'(?:this\s+(?:email|message)|unsubscribe|confidential|disclaimer)', p, re.IGNORECASE):
            continue
        if len(p) > len(best):
            best = p

    return best[:500] if best else None


def _extract_location(text):
    """Extract location from text."""
    # Labeled location
    for pattern in [
        r'location\s*[:\-]\s*([^\n]+)',
        r'(?:located?\s+(?:in|at))\s*[:\-]?\s*([^\n,]{5,}(?:,\s*[A-Z]{2})?)',
        r'(?:city|area|region)\s*[:\-]\s*([^\n]+)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip('.')
            if len(loc) > 2 and len(loc) < 100:
                return loc

    # Look for "City, ST" pattern
    m = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})\b', text)
    if m:
        return m.group(1)

    # Look for county patterns
    m = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+County(?:,\s*[A-Z]{2})?)', text)
    if m:
        return m.group(1)

    return None


def _extract_category(text):
    """Extract business category/industry from text."""
    for pattern in [
        r'(?:category|industry|type|sector)\s*[:\-]\s*([^\n]+)',
        r'(?:type\s+of\s+business)\s*[:\-]\s*([^\n]+)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            cat = m.group(1).strip().rstrip('.')
            if len(cat) > 2 and len(cat) < 100:
                return cat

    return None


def _extract_url(body):
    """Extract the most relevant listing URL from the email body."""
    # Find all URLs
    urls = re.findall(r'https?://[^\s<>"\']+', body)

    if not urls:
        return None

    # Prioritize listing-specific URLs
    listing_keywords = ['listing', 'business', 'for-sale', 'property', 'detail', 'view']
    for url in urls:
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        if any(kw in path_lower for kw in listing_keywords):
            return url.rstrip('.,;:)')

    # Skip common non-listing URLs
    skip_domains = [
        'unsubscribe', 'mailto', 'facebook.com', 'twitter.com',
        'linkedin.com', 'instagram.com', 'youtube.com', 'google.com',
    ]
    for url in urls:
        if not any(skip in url.lower() for skip in skip_domains):
            return url.rstrip('.,;:)')

    return urls[0].rstrip('.,;:)') if urls else None
