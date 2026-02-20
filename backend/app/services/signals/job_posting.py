"""
Job Posting Signal Collector — detects hiring signals that indicate
a company needs services related to the user's capabilities.
"""
import json
import logging
from datetime import datetime

from app.services.signals.base import SignalCollector
from app.services.signals.registry import register_collector

logger = logging.getLogger(__name__)


@register_collector('job_posting')
class JobPostingCollector(SignalCollector):
    """Detects hiring signals via web search."""

    source_type = 'job_posting'

    def collect(self, contact, workspace_id, config=None):
        if not contact.company:
            return []

        from app.models.signal import Signal
        from app.models.settings import Settings

        # Check for existing recent signal to avoid duplicates
        from datetime import timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        existing = Signal.query.filter(
            Signal.contact_id == contact.id,
            Signal.source_type == 'job_posting',
            Signal.dismissed == False,
            Signal.detected_at > seven_days_ago,
        ).first()
        if existing:
            return []

        # Use web search to find job postings
        api_key = Settings.get('tavily_api_key')
        if not api_key:
            return []

        try:
            from app.services.web_search import WebSearchService
            searcher = WebSearchService(api_key)
            results = searcher.search(
                f'"{contact.company}" hiring OR jobs OR careers',
                max_results=3,
                search_depth='basic',
                include_answer=False,
            )

            signals = []
            for result in results.get('results', []):
                title = result.get('title', '')
                content = result.get('content', '')
                url = result.get('url', '')

                # Check if it's actually a job posting
                job_indicators = ['hiring', 'job', 'career', 'position', 'role', 'apply',
                                  'we are looking', 'join our team', 'openings']
                if not any(ind in (title + ' ' + content).lower() for ind in job_indicators):
                    continue

                # Extract job title hints from the content
                job_title = self._extract_job_title(title, content)

                signal = Signal(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    source_type='job_posting',
                    signal_type='hiring',
                    title=f'{contact.company} is hiring: {job_title}' if job_title else f'{contact.company} has open positions',
                    summary=content[:300] if content else title,
                    raw_data=json.dumps({
                        'job_title': job_title,
                        'source_title': title,
                        'source_content': content[:500],
                    }),
                    source_url=url,
                    intent_score=self.score_intent({'job_title': job_title}),
                    intent_category='growth',
                    severity='info',
                )
                signals.append(signal)

                # Only take the first relevant result per contact
                break

            return signals

        except Exception as e:
            logger.error(f'Job posting search failed for {contact.company}: {e}')
            return []

    def _extract_job_title(self, title, content):
        """Try to extract a job title from search result text."""
        import re

        # Common patterns in job listing titles
        patterns = [
            r'hiring\s+(?:a\s+)?(.+?)(?:\s*[-|]|\s*at\b)',
            r'(?:position|role|opening):\s*(.+?)(?:\s*[-|]|\s*$)',
            r'(?:looking for|seeking)\s+(?:a\s+)?(.+?)(?:\s*[-|,.])',
        ]
        combined = f'{title} {content}'
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                job = match.group(1).strip()
                if 3 < len(job) < 80:
                    return job

        return None

    def score_intent(self, signal_data):
        job_title = (signal_data.get('job_title') or '').lower()

        # High-intent keywords (they need external help or are scaling)
        high_intent = ['consultant', 'contractor', 'freelance', 'agency',
                       'outsource', 'vendor', 'partner']
        if any(kw in job_title for kw in high_intent):
            return 0.85

        # Medium-intent (building internal team = still growing)
        medium_intent = ['manager', 'director', 'lead', 'head of', 'vp']
        if any(kw in job_title for kw in medium_intent):
            return 0.7

        # General hiring = growth signal
        return 0.6
