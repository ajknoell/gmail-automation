import re
import requests
from html.parser import HTMLParser
from typing import Optional


class _TextExtractor(HTMLParser):
    """Simple HTML-to-text converter that strips tags."""

    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False
        self._skip_tags = {'script', 'style', 'noscript', 'svg', 'head'}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
        if tag in ('br', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr'):
            self._parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        text = ' '.join(self._parts)
        # Collapse whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()


class WebsiteAnalyzer:

    @staticmethod
    def fetch_website(url: str, timeout: int = 10, max_chars: int = 4000) -> Optional[str]:
        """Fetch a website and return its text content, truncated."""
        if not url:
            return None

        # Ensure URL has a scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; email-outreach-bot/1.0)',
                    'Accept': 'text/html',
                },
                allow_redirects=True,
            )
            resp.raise_for_status()

            content_type = resp.headers.get('content-type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return None

            extractor = _TextExtractor()
            extractor.feed(resp.text)
            text = extractor.get_text()

            if len(text) > max_chars:
                text = text[:max_chars] + '\n[...truncated]'

            return text

        except Exception:
            return None

    @staticmethod
    def url_from_email(email: str) -> Optional[str]:
        """Derive a website URL from an email domain."""
        if not email or '@' not in email:
            return None
        domain = email.split('@')[1].strip().lower()
        # Skip common free email providers
        free_providers = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'icloud.com', 'mail.com', 'protonmail.com',
            'proton.me', 'zoho.com', 'yandex.com',
        }
        if domain in free_providers:
            return None
        return f'https://{domain}'

    @classmethod
    def resolve_url(cls, recipient: dict) -> Optional[str]:
        """Get website URL from custom fields or email domain."""
        custom_fields = recipient.get('custom_fields', {})

        # Check explicit website fields
        for key in ('website', 'url', 'site', 'website_url', 'company_url', 'domain'):
            val = custom_fields.get(key, '').strip()
            if val:
                return val

        # Fall back to email domain
        return cls.url_from_email(recipient.get('email', ''))

    @classmethod
    def fetch_and_analyze(cls, claude_service, recipient: dict, learned_website_insights: dict = None) -> Optional[dict]:
        """Fetch recipient's website and generate improvement insights.

        Returns a dict with 'analysis' (the insight text), 'url', 'company',
        and 'raw_text_preview' for logging, or None if unavailable.
        """
        url = cls.resolve_url(recipient)
        if not url:
            return None

        text = cls.fetch_website(url)
        if not text or len(text) < 50:
            return None

        company = recipient.get('company') or url
        analysis = claude_service.analyze_website(text, company, url, learned_website_insights)
        if not analysis:
            return None

        return {
            'analysis': analysis,
            'url': url,
            'company': company,
            'raw_text_preview': text[:500],
        }
