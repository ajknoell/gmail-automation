import base64
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


def _capture_screenshot(url: str, timeout: int = 20) -> Optional[str]:
    """Capture a full-page screenshot using Playwright and return as base64 PNG.

    Returns None if Playwright is not installed or the capture fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
            # Small extra wait for late-loading widgets (reviews, galleries, etc.)
            page.wait_for_timeout(2000)
            screenshot_bytes = page.screenshot(full_page=True)
            browser.close()

        # If the image is very large, resize to keep token costs reasonable
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(screenshot_bytes))
            max_width = 1280
            max_height = 3000  # Cap very long pages
            if img.width > max_width or img.height > max_height:
                ratio = min(max_width / img.width, max_height / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='PNG', optimize=True)
                screenshot_bytes = buf.getvalue()
        except ImportError:
            pass  # PIL not available, use the raw screenshot

        return base64.b64encode(screenshot_bytes).decode('utf-8')
    except Exception as e:
        print(f"Screenshot capture failed for {url}: {e}")
        return None


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
    def fetch_and_analyze(cls, claude_service, recipient: dict) -> Optional[str]:
        """Fetch recipient's website and generate improvement insights.

        Captures a screenshot for visual analysis when possible, falling back
        to text-only analysis if Playwright is unavailable.

        Returns a string with 2 specific callouts, or None if unavailable.
        """
        url = cls.resolve_url(recipient)
        if not url:
            return None

        # Ensure URL has a scheme for screenshot capture
        screenshot_url = url
        if not screenshot_url.startswith(('http://', 'https://')):
            screenshot_url = 'https://' + screenshot_url

        # Try to capture a screenshot for visual analysis
        screenshot_b64 = _capture_screenshot(screenshot_url)

        # Always fetch text as supplementary context
        text = cls.fetch_website(url)
        if not text or len(text) < 50:
            text = None

        # Need at least one data source
        if not screenshot_b64 and not text:
            return None

        company = recipient.get('company') or url
        return claude_service.analyze_website(
            text, company, url, screenshot_b64=screenshot_b64
        )
