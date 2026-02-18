import hashlib
import json
import re
import time
from typing import Dict, List

import requests


# In-memory cache: cache_key -> {competitors: [...], ts: float}
_competitor_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes


class CompetitorService:
    """Discover competitors by searching for local businesses.

    Primary: Google Places API (returns exact Google Maps results).
    Fallback: Tavily web search + Haiku extraction.
    """

    DEFAULT_QUERY = '{{industry}} in {{city}} {{state}}'

    def __init__(self, web_search_service=None, anthropic_api_key: str = None,
                 google_places_api_key: str = None):
        self.web_search = web_search_service
        self.api_key = anthropic_api_key
        self.google_places_key = google_places_api_key

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

        competitors = []

        # Primary: Google Places API — returns the same businesses as Google Maps
        if self.google_places_key:
            competitors = self._search_google_places(query, company, max_competitors)

        # Fallback: Tavily + Haiku extraction
        if len(competitors) < 2 and self.web_search:
            results = self.web_search.search(
                query=query,
                max_results=10,
                search_depth='advanced',
                include_answer=True,
            )

            tavily_competitors = []
            if self.api_key:
                tavily_competitors = self._extract_with_haiku(results, company, query, max_competitors)
            if len(tavily_competitors) < 2:
                heuristic = self._extract_from_results(results, company, max_competitors)
                if len(heuristic) > len(tavily_competitors):
                    tavily_competitors = heuristic

            if len(tavily_competitors) > len(competitors):
                competitors = tavily_competitors

        _competitor_cache[cache_key] = {
            'competitors': competitors,
            'ts': time.time(),
        }

        return competitors

    def _search_google_places(self, query: str, company: str, max_count: int) -> List[str]:
        """Search Google Places Text Search API for local businesses.

        Returns business names from Google Maps — the same results users see
        when they search on Google.
        """
        try:
            response = requests.get(
                'https://maps.googleapis.com/maps/api/place/textsearch/json',
                params={
                    'query': query,
                    'key': self.google_places_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'OK':
                print(f"Google Places API status: {data.get('status')} - {data.get('error_message', '')}")
                return []

            company_lower = (company or '').lower().strip()
            # Strip common business suffixes for comparison
            company_base = self._strip_business_suffix(company_lower)
            names = []
            for place in data.get('results', []):
                name = place.get('name', '').strip()
                if not name or len(name) < 3 or len(name) > 60:
                    continue
                # Skip if it matches the target company
                name_lower = name.lower()
                name_base = self._strip_business_suffix(name_lower)
                if company_lower and (company_lower in name_lower or name_lower in company_lower
                                      or company_base == name_base):
                    continue
                # Only include operational businesses
                biz_status = place.get('business_status', '')
                if biz_status and biz_status != 'OPERATIONAL':
                    continue
                names.append(name)
                if len(names) >= max_count:
                    break

            return names
        except Exception as e:
            print(f"Google Places search failed: {e}")
            return []

    @staticmethod
    def _strip_business_suffix(name: str) -> str:
        """Strip LLC, Inc, Corp, etc. for comparison."""
        return re.sub(
            r'\s*(llc|inc|corp|ltd|co|company|incorporated|corporation|'
            r'limited|group|services|enterprises?)\.?\s*$',
            '', name, flags=re.IGNORECASE,
        ).strip().rstrip(',').strip()

    @staticmethod
    def _clean_city(value: str) -> str:
        """Strip street address prefixes from a city value.

        If the CSV city field contains '148 Rt 202 Somers' or '123 Main St Somers',
        extract just the city name by removing leading number + street tokens.
        """
        if not value:
            return ''
        value = value.strip()
        # If it doesn't start with a digit, it's probably already a clean city name
        if not value[0].isdigit():
            return value
        # Strip leading "123 Main St" / "148 Rt 202" style prefixes
        # Look for the last word(s) that aren't part of the street address
        # Common pattern: digits + street words + city name
        street_words = {
            'st', 'street', 'ave', 'avenue', 'rd', 'road', 'dr', 'drive',
            'ln', 'lane', 'blvd', 'boulevard', 'ct', 'court', 'pl', 'place',
            'way', 'cir', 'circle', 'rt', 'route', 'hwy', 'highway',
            'pkwy', 'parkway', 'n', 's', 'e', 'w', 'north', 'south',
            'east', 'west', 'ne', 'nw', 'se', 'sw', 'ste', 'suite', 'apt',
            'unit', 'fl', 'floor',
        }
        words = value.split()
        # Walk through words: skip digits and known street tokens
        city_start = 0
        for i, word in enumerate(words):
            clean_word = re.sub(r'[.,#]', '', word).lower()
            if clean_word.isdigit() or clean_word in street_words:
                city_start = i + 1
            else:
                # Once we hit a non-street word after the address portion, stop
                if city_start > 0:
                    break
        if city_start > 0 and city_start < len(words):
            return ' '.join(words[city_start:])
        return value

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
                    # Clean city values that may contain street addresses
                    clean_val = val
                    if key == 'city' and val:
                        clean_val = self._clean_city(val)
                    query = query.replace(placeholder, str(clean_val) if clean_val else '')
        # Remove any remaining unresolved placeholders
        query = re.sub(r'\{\{\w+\}\}', '', query).strip()
        return query

    # Words/phrases that indicate a result is from a directory, not an actual business website
    _DIRECTORY_PATTERNS = re.compile(
        r'\b(top \d+|best \d+|\d+ best|yelp|angi|homeadvisor|thumbtack|bbb|'
        r'better business|yellow pages|mapquest|nextdoor|bark\.com|houzz|'
        r'porch\.com|expertise\.com|google maps)\b',
        re.IGNORECASE,
    )
    # Results that should be completely excluded — not businesses at all
    _JUNK_TITLE_PATTERNS = re.compile(
        r'\b(\.gov|government|department of|city of|county of|state of|'
        r'municipality|public records|vendor list|dod |'
        r'\.pdf|report|filing|permit|license lookup|registry|'
        r'\.edu|university|college|school district|'
        r'wikipedia|wiki|how to|what is|salary|job posting|careers at|'
        r'news|article|blog post)\b',
        re.IGNORECASE,
    )
    # URL patterns for non-business sites
    _JUNK_URL_PATTERNS = re.compile(
        r'\.(gov|edu|mil)(/|$)|\.pdf($|\?)|/wiki/|wikipedia\.org|'
        r'indeed\.com|glassdoor|salary\.com|reddit\.com|quora\.com',
        re.IGNORECASE,
    )
    # Suffixes commonly appended to business names in search titles
    _TITLE_SUFFIXES = re.compile(
        r'\s*[-|–—:]\s*(yelp|reviews|ratings|angi|homeadvisor|thumbtack|'
        r'facebook|linkedin|bbb|google|mapquest|nextdoor|bark|houzz|porch|'
        r'expertise|updated \d{4}|phone|address|directions|hours|'
        r'electrician.*|plumb.*|contractor.*|service.*|serving .*|'
        r'your .*|local .*|residential .*|commercial .*|'
        r'\d{4}|\(\d{3}\).*|www\..*)$',
        re.IGNORECASE,
    )

    def _extract_from_results(
        self, search_results: dict, company: str, max_count: int
    ) -> List[str]:
        """Extract business names from Tavily answer + result titles.

        Priority order:
        1. Tavily answer field (often the best summary)
        2. Organic result titles (actual business websites)
        3. Directory result titles (Yelp, Angi, etc.) as fallback

        Skips government, educational, PDF, and other non-business results entirely.
        """
        company_lower = (company or '').lower().strip()
        seen = set()

        # 1) Parse the answer field — Tavily often lists businesses by name
        answer_names = []
        answer = search_results.get('answer', '')
        if answer:
            # Process line-by-line to prevent greedy cross-line matching
            for line in answer.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Numbered lists: "1. Smith Electric" or "1) Smith Electric"
                m = re.match(r'\d+[.)]\s*\*{0,2}([A-Z][A-Za-z0-9 &.\'-]+)', line)
                if m:
                    answer_names.append(m.group(1).strip().rstrip('.'))
                    continue
                # Bullet lists: "- Smith Electric" or "• Smith Electric"
                m = re.match(r'[-•]\s+([A-Z][A-Za-z0-9 &.\'-]+)', line)
                if m:
                    answer_names.append(m.group(1).strip().rstrip('.'))
                    continue
            # Bold names: **Smith Electric**
            for m in re.finditer(r'\*\*([A-Z][A-Za-z0-9 &.\'-]+?)\*\*', answer):
                answer_names.append(m.group(1).strip())
            # Comma-separated lists: "...include ABC Electric, XYZ Services, and Smith Co"
            comma_m = re.search(
                r'(?:include|such as|like|are|:\s*)'
                r'((?:[A-Z][A-Za-z0-9 &.\'-]+,\s*)+(?:and\s+)?[A-Z][A-Za-z0-9 &.\'-]+)',
                answer,
            )
            if comma_m:
                for part in re.split(r',\s*(?:and\s+)?', comma_m.group(1)):
                    part = part.strip().rstrip('.')
                    if part and part[0].isupper():
                        answer_names.append(part)

        # 2) Split result titles into organic vs directory (skip junk entirely)
        organic_names = []
        directory_names = []
        for r in search_results.get('results', []):
            title = r.get('title', '').strip()
            url = r.get('url', '')
            if not title:
                continue
            # Skip government, educational, PDF, and other non-business results
            if self._JUNK_TITLE_PATTERNS.search(title):
                continue
            if url and self._JUNK_URL_PATTERNS.search(url):
                continue
            # Strip trailing site name / metadata
            cleaned = self._TITLE_SUFFIXES.sub('', title).strip()
            if not cleaned or len(cleaned) <= 2:
                continue
            if self._DIRECTORY_PATTERNS.search(title):
                directory_names.append(cleaned)
            else:
                organic_names.append(cleaned)

        # 3) Merge in priority order: answer first, then organic, then directory fallback
        result = []
        for name in answer_names + organic_names + directory_names:
            name = name.strip().rstrip('.')
            key = name.lower()
            if key in seen:
                continue
            if company_lower and company_lower in key:
                continue
            if len(name) < 3 or len(name) > 60:
                continue
            # Skip names that look institutional/governmental
            if self._JUNK_TITLE_PATTERNS.search(name):
                continue
            seen.add(key)
            result.append(name)
            if len(result) >= max_count:
                break

        return result

    def _extract_with_haiku(
        self, search_results: dict, company: str, search_query: str, max_count: int
    ) -> List[str]:
        """Use Haiku to extract business names from search results."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            # Build a concise text block from the search results — include URLs
            parts = []
            answer = search_results.get('answer', '')
            if answer:
                parts.append(f"Search summary: {answer[:800]}")
            for r in search_results.get('results', [])[:8]:
                title = r.get('title', '')
                url = r.get('url', '')
                content = r.get('content', '')[:200]
                if title:
                    parts.append(f"- {title} ({url}): {content}")
            text = '\n'.join(parts)

            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                messages=[{
                    'role': 'user',
                    'content': (
                        f"I searched Google for: \"{search_query}\"\n\n"
                        f"From these search results, I need the names of real, local "
                        f"businesses that someone would hire when searching for "
                        f"\"{search_query}\". These should be actual companies that "
                        f"DO this type of work — not companies in adjacent industries.\n\n"
                        f"For example, if the search is for 'electricians in Springfield', "
                        f"I want actual electrician companies like 'Joe's Electric' or "
                        f"'Springfield Electrical Services' — NOT energy companies, lighting "
                        f"companies, solar companies, or general contractors.\n\n"
                        f"Return a JSON array of business name strings, max {max_count}.\n\n"
                        f"RULES:\n"
                        f"- Exclude '{company}' and any variation of it\n"
                        f"- ONLY include businesses whose primary service matches the search\n"
                        f"- Exclude companies in adjacent/related industries that don't do this exact work\n"
                        f"- Exclude directories (Yelp, Angi, HomeAdvisor, etc.)\n"
                        f"- Exclude review sites, comparison pages, 'Top 10' articles\n"
                        f"- Exclude government agencies, schools, journals, PDFs\n"
                        f"- Look at the URL — real local businesses have their own website domains\n"
                        f"- If no matching businesses found, return []\n\n"
                        f"RESULTS:\n{text}"
                    ),
                }],
            )

            raw = response.content[0].text.strip()
            # Extract JSON array from response
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                names = json.loads(m.group())
                company_lower = (company or '').lower().strip()
                return [
                    n for n in names
                    if isinstance(n, str)
                    and 3 <= len(n) <= 60
                    and company_lower not in n.lower()
                ][:max_count]
        except Exception as e:
            print(f"Haiku competitor extraction failed: {e}")
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
            f'KNOWN COMPETITORS: These local businesses compete with '
            f'{target}: {names}. '
            f'Competitor variables like {{{{competitor1}}}} have already been '
            f'substituted in the template. '
            f'ONLY use competitor names that appear in this list. '
            f'Do NOT make up competitors, reference search results, mention '
            f'PDFs, government listings, or describe what "shows up on Google." '
            f'If the template references competitors, those are already filled in.'
        )
