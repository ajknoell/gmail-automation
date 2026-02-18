import hashlib
import re
import time
from typing import Dict, List

import requests


# In-memory cache: cache_key -> {competitors: [...], ts: float}
_competitor_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes


class CompetitorService:
    """Discover competitors via Google Places API (same results as Google Maps)."""

    DEFAULT_QUERY = '{{industry}} in {{city}} {{state}}'

    def __init__(self, google_places_api_key: str = None):
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

        if self.google_places_key:
            competitors = self._search_google_places(query, company, max_competitors)

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
