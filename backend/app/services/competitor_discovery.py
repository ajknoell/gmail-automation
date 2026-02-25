import hashlib
import logging
import re
import time
from typing import Dict, List

import requests

from app.services.csv_parser import US_STATES

logger = logging.getLogger(__name__)

# In-memory cache: cache_key -> {competitors: [...], ts: float}
_competitor_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes
_CACHE_MAX_SIZE = 500

# Pre-compiled regex for street-type words (Ave, St, Rd, etc.)
_STREET_TYPE_RE = re.compile(
    r'\b(?:st|street|ave|avenue|rd|road|dr|drive|ln|lane|blvd|boulevard|'
    r'ct|court|pl|place|way|cir|circle|rt|route|hwy|highway|pkwy|parkway)\b',
    re.IGNORECASE,
)

# Address field names to search (case-insensitive scan at runtime)
_ADDRESS_FIELD_KEYWORDS = ('address', 'location', 'street')


class CompetitorService:
    """Discover competitors via Google Places API (same results as Google Maps)."""

    DEFAULT_QUERY = '{{industry}} in {{city}} {{state}}'

    def __init__(self, google_places_api_key: str = None):
        self.google_places_key = google_places_api_key

    def discover_competitors(
        self,
        company: str,
        industry: str = '',
        search_query: str = None,
        max_competitors: int = 5,
        custom_fields: dict = None,
    ) -> Dict:
        """Search for businesses in the same space.

        Returns dict with 'competitors' (list of names) and 'location' (resolved city/state string).
        """
        query_template = search_query or self.DEFAULT_QUERY
        query, location = self._build_query(query_template, company, industry, custom_fields)

        if not query.strip():
            return {'competitors': [], 'location': ''}

        cache_key = self._cache_key(query)

        cached = _competitor_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return {'competitors': cached['competitors'][:max_competitors], 'location': cached.get('location', '')}

        competitors = []

        if self.google_places_key:
            logger.info(f"Google Places query: {query}")
            competitors = self._search_google_places(query, company, max_competitors)
            logger.info(f"Found: {competitors}")

        # Evict expired entries when cache gets large
        if len(_competitor_cache) > _CACHE_MAX_SIZE:
            self._evict_cache()

        _competitor_cache[cache_key] = {
            'competitors': competitors,
            'location': location,
            'ts': time.time(),
        }

        return {'competitors': competitors, 'location': location}

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
                logger.warning(f"Google Places API status: {data.get('status')} - {data.get('error_message', '')}")
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
            logger.error(f"Google Places search failed: {e}")
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

        If the CSV city field contains '148 Rt 202 Somers' or '74 S Main St Pearl River',
        extract just the city name by finding the last street-type word and taking
        everything after it.
        """
        if not value:
            return ''
        value = value.strip()
        # If it doesn't start with a digit, it's probably already a clean city name
        if not value[0].isdigit():
            return value
        # Find the last street-type word and take everything after it as the city
        last_match = None
        for match in _STREET_TYPE_RE.finditer(value):
            last_match = match
        if last_match:
            city = value[last_match.end():].strip()
            # Strip leading route/highway numbers (e.g. "Rt 202 Somers" -> "Somers")
            city = re.sub(r'^\d+\s+', '', city).strip()
            if city:
                return city
        # Fallback: strip leading digits and return remaining text
        stripped = re.sub(r'^\d[\d\s\-]*', '', value).strip()
        return stripped or value

    def _build_query(self, template: str, company: str, industry: str, custom_fields: dict = None) -> tuple:
        """Substitute all variables in the query template.

        Returns (query_string, location_string) where location is the resolved city + state.
        """
        query = template
        query = query.replace('{{company}}', company or '')
        query = query.replace('{{industry}}', industry or '')
        # Substitute any recipient custom field: {{city}}, {{state}}, {{zip}}, etc.
        fields = dict(custom_fields) if custom_fields else {}
        # If city/state are missing, try to extract from an address field
        if not fields.get('city') or not fields.get('state'):
            self._fill_city_state_from_address(fields)
        # Capture resolved city/state for caller
        resolved_city = self._clean_city(fields.get('city', '')) if fields.get('city') else ''
        resolved_state = fields.get('state', '')
        location_parts = [p for p in (resolved_city, resolved_state) if p]
        location = ', '.join(location_parts)

        for key, val in fields.items():
            placeholder = '{{' + key + '}}'
            if placeholder in query:
                # Clean city values that may contain street addresses
                clean_val = val
                if key == 'city' and val:
                    clean_val = self._clean_city(val)
                query = query.replace(placeholder, str(clean_val) if clean_val else '')
        # Remove any remaining unresolved placeholders
        query = re.sub(r'\{\{\w+\}\}', '', query).strip()
        return query, location

    @staticmethod
    def _fill_city_state_from_address(fields: dict) -> None:
        """Extract city and state from an address field when not already present."""
        # Case-insensitive scan for address-like field names
        addr_value = ''
        for field_key, field_val in fields.items():
            if not field_val:
                continue
            lower_key = field_key.lower()
            if any(kw in lower_key for kw in _ADDRESS_FIELD_KEYWORDS):
                addr_value = field_val
                break
        if not addr_value:
            return
        # Match state abbreviation: ", NY 12345" or ", NY" at end (case-insensitive)
        m = re.search(r',\s*([A-Za-z]{2})\s*\d*[-\d]*\s*$', addr_value)
        if not m:
            return
        state_abbr = m.group(1).upper()
        # Validate against known US state abbreviations
        if state_abbr not in US_STATES:
            return
        before_comma = addr_value[:m.start()].strip()
        # Extract city: find the last street-type word and take everything after it
        last_match = None
        for match in _STREET_TYPE_RE.finditer(before_comma):
            last_match = match
        if last_match:
            city_name = before_comma[last_match.end():].strip()
            # If there's a comma in the extracted text (multi-segment address),
            # take only the part after the last comma
            if ',' in city_name:
                city_name = city_name.rsplit(',', 1)[-1].strip()
        else:
            # No street type found — take text after last comma, or last word
            if ',' in before_comma:
                city_name = before_comma.rsplit(',', 1)[-1].strip()
            else:
                words = before_comma.split()
                city_name = words[-1] if words else ''
        if not fields.get('city') and city_name:
            fields['city'] = city_name
        if not fields.get('state') and state_abbr:
            fields['state'] = state_abbr

    @staticmethod
    def _evict_cache() -> None:
        """Remove expired entries from the competitor cache."""
        now = time.time()
        expired = [k for k, v in _competitor_cache.items() if (now - v['ts']) >= _CACHE_TTL]
        for k in expired:
            del _competitor_cache[k]

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
    def build_ai_context(competitors: List[str], company: str = '', location: str = '') -> str:
        """Build a text block for the Claude prompt with competitor info."""
        if not competitors:
            return ''
        names = ', '.join(competitors)
        target = company or "the recipient's company"
        location_phrase = f' in {location}' if location else ''
        return (
            f'KNOWN COMPETITORS: These local businesses compete with '
            f'{target}{location_phrase}: {names}. '
            f'Competitor names like {{{{competitor1}}}} have ALREADY been substituted '
            f'directly into the template text above. They appear as real business names, not placeholders. '
            f'Do NOT add competitor references yourself. If the template body above does not '
            f'already contain competitor names from this list, do NOT inject them. '
            f'Do NOT make up competitors, reference search results, mention '
            f'PDFs, government listings, or describe what "shows up on Google."'
        )
