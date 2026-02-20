"""
News Signal Collector — detects funding, expansion, and growth
signals from company news via web search.
"""
import json
import logging
from datetime import datetime

from app.services.signals.base import SignalCollector
from app.services.signals.registry import register_collector

logger = logging.getLogger(__name__)


@register_collector('news')
class NewsCollector(SignalCollector):
    """Detects funding, expansion, and growth signals from news."""

    source_type = 'news'

    # News patterns and their signal types
    SIGNAL_PATTERNS = {
        'funding': {
            'keywords': ['funding', 'raised', 'series a', 'series b', 'series c',
                         'seed round', 'investment', 'venture capital', 'vc',
                         'million', 'billion'],
            'signal_type': 'funding_round',
            'intent_category': 'growth',
            'severity': 'important',
        },
        'expansion': {
            'keywords': ['expansion', 'new office', 'new location', 'opening',
                         'expanding', 'growth', 'new market', 'launch',
                         'headquarter', 'relocat'],
            'signal_type': 'expansion',
            'intent_category': 'growth',
            'severity': 'info',
        },
        'leadership': {
            'keywords': ['new ceo', 'new cto', 'new cfo', 'appointed', 'hired',
                         'joins as', 'named as', 'promoted to', 'new vp',
                         'chief', 'executive'],
            'signal_type': 'leadership_change',
            'intent_category': 'active_buying',
            'severity': 'important',
        },
        'product': {
            'keywords': ['launches', 'announces', 'new product', 'new service',
                         'rebrand', 'pivot', 'partnership', 'acquisition',
                         'acquired', 'merger'],
            'signal_type': 'product_launch',
            'intent_category': 'growth',
            'severity': 'info',
        },
    }

    def collect(self, contact, workspace_id, config=None):
        if not contact.company:
            return []

        from app.models.signal import Signal
        from app.models.settings import Settings

        # Check for existing recent signal to avoid duplicates
        from datetime import timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        existing_count = Signal.query.filter(
            Signal.contact_id == contact.id,
            Signal.source_type == 'news',
            Signal.detected_at > seven_days_ago,
        ).count()
        if existing_count >= 3:
            return []

        api_key = Settings.get('tavily_api_key')
        if not api_key:
            return []

        try:
            from app.services.web_search import WebSearchService
            searcher = WebSearchService(api_key)
            results = searcher.search(
                f'"{contact.company}" news OR announcement OR funding OR expansion',
                max_results=5,
                search_depth='basic',
                include_answer=False,
            )

            signals = []
            seen_types = set()

            for result in results.get('results', []):
                title = result.get('title', '')
                content = result.get('content', '')
                url = result.get('url', '')
                combined = f'{title} {content}'.lower()

                # Match against signal patterns
                for pattern_name, pattern in self.SIGNAL_PATTERNS.items():
                    if pattern_name in seen_types:
                        continue

                    matched_keywords = [kw for kw in pattern['keywords'] if kw in combined]
                    if not matched_keywords:
                        continue

                    # Check for duplicate
                    existing = Signal.query.filter(
                        Signal.contact_id == contact.id,
                        Signal.source_type == 'news',
                        Signal.signal_type == pattern['signal_type'],
                        Signal.dismissed == False,
                        Signal.detected_at > seven_days_ago,
                    ).first()
                    if existing:
                        seen_types.add(pattern_name)
                        continue

                    signal = Signal(
                        workspace_id=workspace_id,
                        contact_id=contact.id,
                        source_type='news',
                        signal_type=pattern['signal_type'],
                        title=f'{contact.company}: {title[:200]}',
                        summary=content[:300] if content else title,
                        raw_data=json.dumps({
                            'pattern': pattern_name,
                            'matched_keywords': matched_keywords,
                            'source_title': title,
                            'source_content': content[:500],
                        }),
                        source_url=url,
                        intent_score=self.score_intent({
                            'pattern': pattern_name,
                            'keyword_count': len(matched_keywords),
                        }),
                        intent_category=pattern['intent_category'],
                        severity=pattern['severity'],
                    )
                    signals.append(signal)
                    seen_types.add(pattern_name)

            return signals

        except Exception as e:
            logger.error(f'News search failed for {contact.company}: {e}')
            return []

    def score_intent(self, signal_data):
        pattern = signal_data.get('pattern', '')
        keyword_count = signal_data.get('keyword_count', 0)

        base_scores = {
            'funding': 0.85,
            'leadership': 0.75,
            'expansion': 0.7,
            'product': 0.6,
        }
        base = base_scores.get(pattern, 0.5)

        # Bonus for multiple keyword matches (more confident detection)
        bonus = min(0.1, keyword_count * 0.02)
        return min(1.0, base + bonus)
