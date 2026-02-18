import hashlib
import re
import time
from typing import Dict, List


# In-memory cache: cache_key -> {competitors: [...], ts: float}
_competitor_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes


class CompetitorService:
    """Discover competitors for a company using Tavily web search."""

    DEFAULT_QUERY = '{{company}} top competitors {{industry}}'

    def __init__(self, web_search_service, claude_service=None):
        self.web_search = web_search_service
        self.claude = claude_service

    def discover_competitors(
        self,
        company: str,
        domain: str = '',
        industry: str = '',
        search_query: str = None,
        max_competitors: int = 5,
    ) -> List[str]:
        """Find competitors for a company. Returns list of company names."""
        if not company:
            return []

        query_template = search_query or self.DEFAULT_QUERY
        cache_key = self._cache_key(domain or company, query_template)

        cached = _competitor_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['competitors'][:max_competitors]

        query = self._build_query(query_template, company, industry)
        results = self.web_search.search(
            query=query,
            max_results=5,
            search_depth='basic',
            include_answer=True,
        )

        competitors = self._extract_competitor_names(results, company, max_competitors)

        _competitor_cache[cache_key] = {
            'competitors': competitors,
            'ts': time.time(),
        }

        return competitors

    def _build_query(self, template: str, company: str, industry: str) -> str:
        query = template
        query = query.replace('{{company}}', company or '')
        query = query.replace('{{industry}}', industry or '')
        query = re.sub(r'\{\{\w+\}\}', '', query).strip()
        return query

    def _extract_competitor_names(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        if self.claude:
            try:
                return self._extract_with_claude(search_results, company, max_count)
            except Exception:
                pass
        return self._extract_heuristic(search_results, company, max_count)

    def _extract_with_claude(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        from app.services.web_search import WebSearchService
        context = WebSearchService.format_for_prompt(search_results, max_chars=1500)
        if not context.strip():
            return []

        prompt = (
            f'From the search results below, extract up to {max_count} competitor '
            f'company names for "{company}". Return ONLY a JSON array of strings, '
            f'e.g. ["Acme Corp", "FooBar Inc"]. Do not include "{company}" itself. '
            f'If no competitors are found, return [].\n\n'
            f'Search results:\n{context}'
        )

        response = self.claude.client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}],
        )
        import json
        text = response.content[0].text.strip()
        # Handle markdown code blocks
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()
        competitors = json.loads(text)
        if isinstance(competitors, list):
            return [str(c).strip() for c in competitors if c][:max_count]
        return []

    def _extract_heuristic(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        answer = search_results.get('answer', '')
        if not answer:
            return []
        # Look for numbered lists: "1. CompanyName" or "1) CompanyName"
        numbered = re.findall(r'\d+[.)]\s*([A-Z][A-Za-z0-9\s&.]+)', answer)
        if numbered:
            names = [n.strip().rstrip('.') for n in numbered
                     if company.lower() not in n.lower()]
            return names[:max_count]
        return []

    @staticmethod
    def _cache_key(domain: str, query_template: str) -> str:
        raw = f'{domain.lower()}|{query_template}'
        return hashlib.md5(raw.encode()).hexdigest()

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
