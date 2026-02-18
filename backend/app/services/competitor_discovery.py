import hashlib
import re
import time
from typing import Dict, List


# In-memory cache: cache_key -> {competitors: [...], ts: float}
_competitor_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes


class CompetitorService:
    """Discover competitors by searching for local businesses via Tavily."""

    DEFAULT_QUERY = '{{industry}} in {{city}} {{state}}'

    def __init__(self, web_search_service):
        self.web_search = web_search_service

    def discover_competitors(
        self,
        company: str,
        domain: str = '',
        industry: str = '',
        search_query: str = None,
        max_competitors: int = 5,
        custom_fields: dict = None,
    ) -> List[str]:
        """Search for businesses in the same space and return names excluding the target company."""
        query_template = search_query or self.DEFAULT_QUERY
        query = self._build_query(query_template, company, industry, custom_fields)

        if not query.strip():
            return []

        cache_key = self._cache_key(query)

        cached = _competitor_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['competitors'][:max_competitors]

        results = self.web_search.search(
            query=query,
            max_results=8,
            search_depth='basic',
            include_answer=True,
        )

        competitors = self._extract_from_results(results, company, max_competitors)

        _competitor_cache[cache_key] = {
            'competitors': competitors,
            'ts': time.time(),
        }

        return competitors

    def _build_query(self, template: str, company: str, industry: str, custom_fields: dict = None) -> str:
        """Substitute all variables in the query template."""
        query = template
        query = query.replace('{{company}}', company or '')
        query = query.replace('{{industry}}', industry or '')
        # Substitute any recipient custom field: {{city}}, {{state}}, {{zip}}, etc.
        if custom_fields:
            for key, val in custom_fields.items():
                placeholder = '{{' + key + '}}'
                if placeholder in query:
                    query = query.replace(placeholder, str(val) if val else '')
        # Remove any remaining unresolved placeholders
        query = re.sub(r'\{\{\w+\}\}', '', query).strip()
        return query

    # Words/phrases that indicate a result title is a directory page, not a business
    _SKIP_TITLE_PATTERNS = re.compile(
        r'\b(top \d+|best \d+|\d+ best|yelp|angi|homeadvisor|thumbtack|bbb|'
        r'better business|yellow pages|mapquest|nextdoor|bark\.com|houzz|'
        r'porch\.com|expertise\.com|google maps)\b',
        re.IGNORECASE,
    )
    # Suffixes commonly appended to business names in search titles
    _TITLE_SUFFIXES = re.compile(
        r'\s*[-|–—:]\s*(yelp|reviews|ratings|angi|homeadvisor|thumbtack|'
        r'facebook|linkedin|bbb|google|mapquest|nextdoor|bark|houzz|porch|'
        r'expertise|updated \d{4}|phone|address|directions|hours|'
        r'\d{4}|\(\d{3}\).*|www\..*)$',
        re.IGNORECASE,
    )

    def _extract_from_results(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        """Extract business names from Tavily answer + result titles. No LLM needed."""
        company_lower = (company or '').lower().strip()
        seen = set()
        names = []

        # 1) Parse the answer field — Tavily often lists businesses by name
        answer = search_results.get('answer', '')
        if answer:
            # Numbered lists: "1. Smith Electric" or "1) Smith Electric"
            for m in re.finditer(r'\d+[.)]\s*\*{0,2}([A-Z][A-Za-z0-9\s&.\'-]+)', answer):
                names.append(m.group(1).strip().rstrip('.'))
            # Bold names: **Smith Electric**
            for m in re.finditer(r'\*\*([A-Z][A-Za-z0-9\s&.\'-]+?)\*\*', answer):
                names.append(m.group(1).strip())

        # 2) Extract from result titles — these often ARE the business name
        for r in search_results.get('results', []):
            title = r.get('title', '').strip()
            if not title:
                continue
            # Skip directory/aggregator pages
            if self._SKIP_TITLE_PATTERNS.search(title):
                continue
            # Strip trailing site name / metadata
            cleaned = self._TITLE_SUFFIXES.sub('', title).strip()
            if cleaned and len(cleaned) > 2:
                names.append(cleaned)

        # Dedupe and filter
        result = []
        for name in names:
            name = name.strip().rstrip('.')
            key = name.lower()
            if key in seen:
                continue
            if company_lower and company_lower in key:
                continue
            # Skip if too generic (single word under 4 chars) or too long
            if len(name) < 3 or len(name) > 60:
                continue
            seen.add(key)
            result.append(name)
            if len(result) >= max_count:
                break

        return result

    @staticmethod
    def _cache_key(query: str) -> str:
        return hashlib.md5(query.lower().encode()).hexdigest()

    @staticmethod
    def build_variable_map(competitors: List[str]) -> Dict[str, str]:
        """Convert competitor list to template variable entries.

        Returns: {'competitor1': 'Acme', 'competitor2': 'FooCo', 'competitors': 'Acme, FooCo'}
        """
        var_map = {}
        for i, name in enumerate(competitors, 1):
            var_map[f'competitor{i}'] = name
        if competitors:
            var_map['competitors'] = ', '.join(competitors)
        return var_map

    @staticmethod
    def build_ai_context(competitors: List[str], company: str = '') -> str:
        """Build a text block for the Claude prompt with competitor info."""
        if not competitors:
            return ''
        names = ', '.join(competitors)
        target = company or "the recipient's company"
        return (
            f'KNOWN COMPETITORS: The following companies compete with '
            f'{target}: {names}. '
            f'If the email template references competitors by variable (e.g. '
            f'{{{{competitor1}}}}), those have already been substituted. '
            f'You may also naturally reference these competitors if it adds '
            f'value to the email.'
        )
