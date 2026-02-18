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

        competitors = self._extract_business_names(results, company, max_competitors)

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

    def _extract_business_names(
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
        context = WebSearchService.format_for_prompt(search_results, max_chars=2000)
        if not context.strip():
            return []

        company_lower = (company or '').lower()
        exclude_note = f' Do not include "{company}" or any variation of it.' if company else ''

        prompt = (
            f'From the search results below, extract up to {max_count} real business '
            f'or company names that appear as local competitors or similar businesses.{exclude_note}\n\n'
            f'Rules:\n'
            f'- Return ONLY a JSON array of strings, e.g. ["Smith Electric", "ABC Plumbing"]\n'
            f'- Extract actual business names, not generic terms or website names\n'
            f'- Prefer businesses that appear in listings, directories, or review sites\n'
            f'- If no business names are found, return []\n\n'
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
        names = json.loads(text)
        if isinstance(names, list):
            # Filter out the target company
            filtered = []
            for name in names:
                name_str = str(name).strip()
                if not name_str:
                    continue
                if company_lower and company_lower in name_str.lower():
                    continue
                filtered.append(name_str)
            return filtered[:max_count]
        return []

    def _extract_heuristic(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        answer = search_results.get('answer', '')
        if not answer:
            return []
        company_lower = (company or '').lower()
        # Look for numbered lists: "1. CompanyName" or "1) CompanyName"
        numbered = re.findall(r'\d+[.)]\s*([A-Z][A-Za-z0-9\s&.\'-]+)', answer)
        if numbered:
            names = [n.strip().rstrip('.') for n in numbered
                     if not company_lower or company_lower not in n.lower()]
            return names[:max_count]
        return []

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
