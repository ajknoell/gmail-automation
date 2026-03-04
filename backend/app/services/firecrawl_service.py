"""
Firecrawl Service — thin wrapper around the Firecrawl REST API.
Provides scrape, crawl, and map capabilities for agent-driven web research.
"""
import time
import logging
import threading

import requests

logger = logging.getLogger(__name__)

FIRECRAWL_BASE_URL = 'https://api.firecrawl.dev/v1'

# Rate limiting: minimum seconds between requests
_MIN_REQUEST_INTERVAL = 1.0
_lock = threading.Lock()
_last_request_time = 0.0


def _rate_limit():
    """Enforce minimum interval between Firecrawl API calls."""
    global _last_request_time
    with _lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()


class FirecrawlService:
    """Wrapper around the Firecrawl REST API."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

    @classmethod
    def from_settings(cls):
        """Create instance from stored Settings (DB) or env var."""
        from app.models.settings import Settings
        from config import Config

        api_key = Settings.get('firecrawl_api_key') or Config.FIRECRAWL_API_KEY
        if not api_key:
            raise ValueError('Firecrawl API key not configured')
        return cls(api_key)

    def scrape_url(self, url, formats=None, only_main_content=True):
        """
        Scrape a single page and return its content as markdown.

        Args:
            url: The URL to scrape.
            formats: List of output formats (default: ['markdown']).
            only_main_content: Whether to exclude navs/footers/etc.

        Returns:
            dict with keys: markdown, metadata, success
        """
        _rate_limit()

        payload = {
            'url': url,
            'formats': formats or ['markdown'],
            'onlyMainContent': only_main_content,
        }

        try:
            resp = requests.post(
                f'{FIRECRAWL_BASE_URL}/scrape',
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                'success': data.get('success', False),
                'markdown': data.get('data', {}).get('markdown', ''),
                'metadata': data.get('data', {}).get('metadata', {}),
            }
        except requests.exceptions.HTTPError as e:
            logger.warning(f'Firecrawl scrape failed for {url}: {e}')
            return {
                'success': False,
                'markdown': '',
                'metadata': {},
                'error': str(e),
            }
        except Exception as e:
            logger.error(f'Firecrawl scrape error for {url}: {e}')
            return {
                'success': False,
                'markdown': '',
                'metadata': {},
                'error': str(e),
            }

    def map_site(self, url, limit=50):
        """
        Discover all URLs on a site using Firecrawl's map endpoint.

        Args:
            url: The base URL to map.
            limit: Max number of URLs to return.

        Returns:
            dict with keys: links (list of URLs), success
        """
        _rate_limit()

        payload = {
            'url': url,
            'limit': limit,
        }

        try:
            resp = requests.post(
                f'{FIRECRAWL_BASE_URL}/map',
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                'success': data.get('success', False),
                'links': data.get('links', []),
            }
        except requests.exceptions.HTTPError as e:
            logger.warning(f'Firecrawl map failed for {url}: {e}')
            return {'success': False, 'links': [], 'error': str(e)}
        except Exception as e:
            logger.error(f'Firecrawl map error for {url}: {e}')
            return {'success': False, 'links': [], 'error': str(e)}

    def crawl_site(self, url, max_pages=10, poll_interval=5, max_wait=120):
        """
        Crawl a site asynchronously and poll for results.

        Args:
            url: The starting URL to crawl.
            max_pages: Maximum number of pages to crawl.
            poll_interval: Seconds between status polls.
            max_wait: Maximum seconds to wait for completion.

        Returns:
            dict with keys: pages (list of {url, markdown, metadata}), success
        """
        _rate_limit()

        payload = {
            'url': url,
            'limit': max_pages,
            'scrapeOptions': {
                'formats': ['markdown'],
                'onlyMainContent': True,
            },
        }

        try:
            # Start the crawl
            resp = requests.post(
                f'{FIRECRAWL_BASE_URL}/crawl',
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get('success'):
                return {'success': False, 'pages': [], 'error': 'Crawl start failed'}

            crawl_id = data.get('id')
            if not crawl_id:
                return {'success': False, 'pages': [], 'error': 'No crawl ID returned'}

            # Poll for results
            elapsed = 0
            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval

                status_resp = requests.get(
                    f'{FIRECRAWL_BASE_URL}/crawl/{crawl_id}',
                    headers=self.headers,
                    timeout=15,
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()

                status = status_data.get('status')
                if status == 'completed':
                    pages = []
                    for item in status_data.get('data', []):
                        pages.append({
                            'url': item.get('metadata', {}).get('sourceURL', ''),
                            'markdown': item.get('markdown', ''),
                            'metadata': item.get('metadata', {}),
                        })
                    return {'success': True, 'pages': pages}
                elif status in ('failed', 'cancelled'):
                    return {'success': False, 'pages': [], 'error': f'Crawl {status}'}

            return {'success': False, 'pages': [], 'error': 'Crawl timed out'}

        except Exception as e:
            logger.error(f'Firecrawl crawl error for {url}: {e}')
            return {'success': False, 'pages': [], 'error': str(e)}
