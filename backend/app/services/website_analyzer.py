import base64
import re
import requests
from html.parser import HTMLParser
from typing import Dict, List, Optional


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


def _check_website_health(url: str, timeout: int = 10) -> List[str]:
    """Run pre-flight checks on a URL and return a list of critical issues.

    Checks for SSL errors, HTTP error codes, redirect problems, domain
    parking pages, and other issues a visitor would hit immediately.

    Returns an empty list if everything looks fine.
    """
    issues: List[str] = []

    # Ensure URL has a scheme
    check_url = url
    if not check_url.startswith(('http://', 'https://')):
        check_url = 'https://' + check_url

    # --- SSL / Connection check ---
    try:
        resp = requests.get(
            check_url,
            timeout=timeout,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html',
            },
            allow_redirects=True,
        )
    except requests.exceptions.SSLError as e:
        err = str(e).lower()
        if 'certificate' in err and 'expire' in err:
            issues.append('SSL_CERT_EXPIRED: The site\'s SSL certificate has expired — browsers show a scary security warning before visitors can enter.')
        elif 'certificate' in err:
            issues.append('SSL_CERT_INVALID: The site has an invalid SSL certificate — visitors see a "Your connection is not private" browser warning.')
        else:
            issues.append(f'SSL_ERROR: The site has an SSL/security issue — visitors see a browser security warning. Detail: {e}')
        return issues
    except requests.exceptions.ConnectionError:
        issues.append('CONNECTION_FAILED: The website could not be reached — it may be down or the domain may not be configured.')
        return issues
    except requests.exceptions.Timeout:
        issues.append('TIMEOUT: The website took too long to respond — visitors will leave before the page loads.')
        return issues
    except requests.exceptions.TooManyRedirects:
        issues.append('REDIRECT_LOOP: The website is stuck in a redirect loop — visitors see an error page.')
        return issues
    except Exception as e:
        issues.append(f'CONNECTION_ERROR: Could not connect to the website. Detail: {e}')
        return issues

    # --- Page speed check ---
    load_time = resp.elapsed.total_seconds()
    if load_time > 3:
        issues.append(
            f'SLOW_LOAD: The website took {load_time:.1f} seconds to respond '
            f'— visitors expect pages to load in under 3 seconds and may leave before the site appears.'
        )

    # --- HTTP status code check ---
    if resp.status_code >= 500:
        issues.append(f'SERVER_ERROR: The website returns a {resp.status_code} server error — visitors see an error page.')
    elif resp.status_code == 403:
        issues.append('ACCESS_DENIED: The website returns a 403 Forbidden — visitors are blocked from viewing the site.')
    elif resp.status_code == 404:
        issues.append('NOT_FOUND: The website\'s homepage returns a 404 — visitors land on a "page not found" error.')
    elif resp.status_code >= 400:
        issues.append(f'HTTP_ERROR: The website returns a {resp.status_code} error — visitors can\'t view the page normally.')

    # --- Redirect to a different domain (possible parking/hijack) ---
    if resp.url and resp.history:
        from urllib.parse import urlparse
        original_domain = urlparse(check_url).netloc.lower().replace('www.', '')
        final_domain = urlparse(resp.url).netloc.lower().replace('www.', '')
        if original_domain != final_domain:
            # Check if it's a known parking/registrar domain
            parking_indicators = [
                'godaddy', 'sedoparking', 'hugedomains', 'dan.com',
                'afternic', 'namecheap', 'bodis', 'parked', 'parking',
                'undeveloped', 'domainmarket',
            ]
            if any(p in final_domain for p in parking_indicators):
                issues.append(f'DOMAIN_PARKED: The domain redirects to {final_domain} — the site appears to be parked/for sale, not an active business website.')
            else:
                issues.append(f'UNEXPECTED_REDIRECT: The site redirects to a different domain ({final_domain}) — visitors may not reach the intended site.')

    # --- Content checks (only if we got a 200-level response) ---
    if resp.ok:
        content_type = resp.headers.get('content-type', '')
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            issues.append(f'NOT_HTML: The URL returns {content_type} instead of a web page.')
        else:
            body_lower = resp.text[:5000].lower()

            # Check for domain parking / placeholder pages
            parking_phrases = [
                'this domain is for sale',
                'buy this domain',
                'domain parking',
                'this site is under construction',
                'parked by',
                'this page is parked',
                'domain has expired',
                'website coming soon',
                'future home of',
            ]
            for phrase in parking_phrases:
                if phrase in body_lower:
                    issues.append(f'PARKED_OR_PLACEHOLDER: The site appears to be a placeholder page ("{phrase}" detected) — visitors don\'t see a real business website.')
                    break

            # Check for scam/malware/scareware content
            scam_phrases = [
                'your pc is infected',
                'your computer is infected',
                'virus detected',
                'viruses found',
                'your system is heavily damaged',
                'your pc has been compromised',
                'immediate action required',
                'mcafee total protection',
                'norton security warning',
                'windows defender alert',
                'call microsoft support',
                'your subscription has expired',
                'renew your antivirus',
                'click here to protect',
                'scan your computer',
                'threats detected',
                'your device is at risk',
            ]
            for phrase in scam_phrases:
                if phrase in body_lower:
                    issues.append(
                        'SCAM_OR_MALWARE: The website is showing fake virus warnings or scam popups instead of business content — visitors see a scary fake alert and leave immediately (or worse, get scammed). The domain may be compromised or hijacked by malicious ads.'
                    )
                    break

            # Check for outdated copyright year
            from datetime import datetime as _dt
            copyright_years = re.findall(
                r'(?:©|\(c\)|copyright)\s*(\d{4})', body_lower
            )
            if copyright_years:
                newest_year = max(int(y) for y in copyright_years)
                current_year = _dt.now().year
                if current_year - newest_year >= 2:
                    issues.append(
                        f'OUTDATED_COPYRIGHT: The website\'s copyright year is {newest_year} '
                        f'— the site may not be actively maintained, which can make the business look inactive or outdated to visitors.'
                    )

            # Check for "not secure" / mixed-content hints in page title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', body_lower)
            if title_match:
                title = title_match.group(1)
                if any(w in title for w in ['not secure', 'privacy error', 'deceptive site', 'connection is not private']):
                    issues.append('SECURITY_WARNING_IN_TITLE: The page title contains a security warning — the site may have SSL or security issues.')

    return issues


def _capture_screenshot(
    url: str, timeout: int = 20, ignore_ssl: bool = False
) -> Optional[str]:
    """Capture a full-page screenshot using Playwright and return as base64 PNG.

    When ``ignore_ssl`` is True, Chromium is launched with
    ``--ignore-certificate-errors`` so we can capture what the browser
    actually shows for sites with SSL problems (the warning page itself).

    Returns None if Playwright is not installed or the capture fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            launch_args = []
            if ignore_ssl:
                launch_args.append('--ignore-certificate-errors')
            browser = p.chromium.launch(headless=True, args=launch_args)
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            try:
                page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
            except Exception:
                # Even if navigation fails (e.g. SSL), capture whatever is shown
                pass
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


def _capture_mobile_screenshot(
    url: str, timeout: int = 20, ignore_ssl: bool = False
) -> Optional[str]:
    """Capture a mobile-viewport screenshot (375x812, iPhone-style).

    Returns base64 PNG or None if Playwright is unavailable / capture fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            launch_args = []
            if ignore_ssl:
                launch_args.append('--ignore-certificate-errors')
            browser = p.chromium.launch(headless=True, args=launch_args)
            page = browser.new_page(
                viewport={'width': 375, 'height': 812},
                user_agent=(
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                    'Version/17.0 Mobile/15E148 Safari/604.1'
                ),
            )
            try:
                page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            screenshot_bytes = page.screenshot(full_page=True)
            browser.close()

        # Resize if too large
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(screenshot_bytes))
            max_width = 375
            max_height = 2000
            if img.width > max_width or img.height > max_height:
                ratio = min(max_width / img.width, max_height / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='PNG', optimize=True)
                screenshot_bytes = buf.getvalue()
        except ImportError:
            pass

        return base64.b64encode(screenshot_bytes).decode('utf-8')
    except Exception as e:
        print(f"Mobile screenshot capture failed for {url}: {e}")
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
    def fetch_inner_pages(cls, base_url: str, max_chars: int = 1500) -> Optional[str]:
        """Fetch key inner pages (/about, /services, /contact) and return combined text.

        Skips pages that redirect back to the homepage or return errors.
        Returns None if no meaningful inner-page content was found.
        """
        from urllib.parse import urlparse, urljoin

        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url

        # Normalise: ensure trailing slash for urljoin
        if not base_url.endswith('/'):
            base_url += '/'

        homepage_path = urlparse(base_url).path
        inner_paths = ['/about', '/about-us', '/services', '/contact']
        parts: List[str] = []

        for path in inner_paths:
            page_url = urljoin(base_url, path)
            try:
                resp = requests.get(
                    page_url,
                    timeout=5,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; email-outreach-bot/1.0)',
                        'Accept': 'text/html',
                    },
                    allow_redirects=True,
                )
                if not resp.ok:
                    continue

                # Skip if it redirected back to the homepage
                final_path = urlparse(resp.url).path.rstrip('/')
                if final_path == homepage_path.rstrip('/') or final_path == '':
                    continue

                content_type = resp.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    continue

                extractor = _TextExtractor()
                extractor.feed(resp.text)
                text = extractor.get_text()
                if text and len(text) > 50:
                    parts.append(f'--- {path} ---\n{text[:800]}')
            except Exception:
                continue

        if not parts:
            return None

        combined = '\n\n'.join(parts)
        if len(combined) > max_chars:
            combined = combined[:max_chars] + '\n[...truncated]'
        return combined

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

        Runs health checks first to detect critical issues (SSL errors,
        broken pages, parked domains).  Then captures a screenshot for
        visual analysis, falling back to text-only when Playwright is
        unavailable.

        Returns a dict with 'analysis' (the insight text), 'url', 'company',
        and 'raw_text_preview' for logging, or None if unavailable.
        """
        url = cls.resolve_url(recipient)
        if not url:
            return None

        # Ensure URL has a scheme
        screenshot_url = url
        if not screenshot_url.startswith(('http://', 'https://')):
            screenshot_url = 'https://' + screenshot_url

        # --- Step 1: Pre-flight health checks ---
        health_issues = _check_website_health(screenshot_url)
        has_ssl_issue = any(
            tag in issue for issue in health_issues
            for tag in ('SSL_', 'SECURITY_WARNING')
        )

        # --- Step 2: Capture screenshots (desktop + mobile) ---
        # If there's an SSL issue, capture with ignore_ssl so we see what
        # the browser actually shows (the warning page).
        screenshot_b64 = _capture_screenshot(
            screenshot_url, ignore_ssl=has_ssl_issue
        )
        mobile_screenshot_b64 = _capture_mobile_screenshot(
            screenshot_url, ignore_ssl=has_ssl_issue
        )

        # --- Step 3: Fetch text as supplementary context ---
        text = None
        # Skip text fetch if the site has connection-level issues
        connection_failures = ('CONNECTION_FAILED', 'TIMEOUT', 'REDIRECT_LOOP')
        if not any(tag in issue for issue in health_issues for tag in connection_failures):
            try:
                text = cls.fetch_website(url)
                if not text or len(text) < 50:
                    text = None
            except Exception:
                text = None

            # --- Step 3b: Fetch key inner pages for richer context ---
            if text:
                try:
                    inner_text = cls.fetch_inner_pages(url)
                    if inner_text:
                        text = text + '\n\n' + inner_text
                except Exception:
                    pass

        # Need at least one data source (issues alone count — they tell us
        # plenty about what visitors experience)
        if not screenshot_b64 and not text and not health_issues:
            return None

        company = recipient.get('company')
        if not company:
            # Extract a readable name from the domain instead of using the raw URL
            from urllib.parse import urlparse
            parsed = urlparse(url if '://' in url else f'https://{url}')
            domain = parsed.hostname or url
            # Strip common prefixes like 'www.'
            if domain.startswith('www.'):
                domain = domain[4:]
            # Use just the domain name part (e.g. "acmestartup" from "acmestartup.com")
            company = domain.split('.')[0].capitalize()
        analysis = claude_service.analyze_website(
            text,
            company,
            url,
            screenshot_b64=screenshot_b64,
            mobile_screenshot_b64=mobile_screenshot_b64,
            health_issues=health_issues,
            learned_website_insights=learned_website_insights,
        )
        if not analysis:
            return None

        return {
            'analysis': analysis,
            'url': url,
            'company': company,
            'raw_text_preview': (text[:500] if text else ''),
        }
